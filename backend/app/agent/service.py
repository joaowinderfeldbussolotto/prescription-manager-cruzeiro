"""Monta e expõe o agente real (LangChain + Groq) usado pelo chat "Agente".

Construído uma única vez, na importação deste módulo (mesmo padrão de
`settings = get_settings()` em `app/config.py`) — SE `GROQ_API_KEY` estiver
configurada; caso contrário `AGENT` fica `None` e o router trata isso como
feature indisponível (mesmo padrão dos outros toggles do projeto: 404).

Observabilidade (Langfuse) é opcional e aditiva: sem `LANGFUSE_SECRET_KEY`/
`LANGFUSE_PUBLIC_KEY` configuradas, o agente funciona igual, só sem tracing
e usando o prompt local em vez do gerenciado no Langfuse.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from langchain.agents import create_agent
from langchain.agents.middleware import ModelFallbackMiddleware
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.mongodb import MongoDBSaver
from pymongo import MongoClient

from app.agent.tools import TOOLS
from app.config import settings

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "system_prompt.md"

# create_agent não limita mais a recursão por padrão (usa um teto interno
# bem alto) — sem isso, uma tool que falha repetidamente pendura a request.
_RECURSION_LIMIT = 12
_TIMEOUT_SECONDS = 45

_MENSAGEM_ERRO = (
    "Não consegui processar sua mensagem agora (instabilidade do serviço de "
    "IA). Tente novamente em instantes."
)

_sync_client: MongoClient | None = None
AGENT = None

# --- Langfuse (tracing + prompt management) — opcional, aditivo -------------
_langfuse_client = None
_langfuse_handler = None

if settings.langfuse_secret_key and settings.langfuse_public_key:
    try:
        from langfuse import get_client
        from langfuse.langchain import CallbackHandler

        # get_client()/CallbackHandler() leem LANGFUSE_SECRET_KEY/
        # LANGFUSE_PUBLIC_KEY/LANGFUSE_BASE_URL direto do ambiente do
        # processo (o docker-compose já injeta essas variáveis no
        # container) — não repassamos as settings manualmente pro SDK.
        _langfuse_client = get_client()
        _langfuse_handler = CallbackHandler()
    except Exception:
        logger.exception("Falha ao inicializar Langfuse — seguindo sem tracing")
        _langfuse_client = None
        _langfuse_handler = None
else:
    logger.info("Langfuse não configurado — Agente seguirá sem tracing")

# NUNCA colocar `_LANGFUSE_PROMPT_OBJ` (um TextPromptClient) dentro do
# `metadata` passado pro `.ainvoke()` do agente: o LangGraph mescla esse
# dict no CheckpointMetadata que o MongoDBSaver persiste a cada checkpoint,
# serializando via msgpack — e TextPromptClient não é um tipo primitivo
# (`TypeError: Type is not msgpack serializable`, visto em produção). Esse
# padrão (`config={"metadata": {"langfuse_prompt": prompt}}`) só é seguro
# em chains simples do LangChain sem checkpointer — o próprio time do
# Langfuse confirma que ainda não há suporte limpo pra isso com LangGraph
# (github.com/orgs/langfuse/discussions/11825). Em vez disso, associamos o
# prompt à GERAÇÃO ativa via `update_current_generation(prompt=...)`, que
# fala com o Langfuse direto pela API do SDK, sem passar pelo estado
# persistido do LangGraph — só funciona dentro de um span já aberto por
# `@observe()` (ver `enviar_mensagem` abaixo).


def _load_system_prompt() -> tuple[str, object | None]:
    """Busca o prompt do Langfuse (Prompt Management); cai pro arquivo local
    se Langfuse não estiver configurado ou a busca falhar.

    Retorna ``(texto_do_prompt, objeto_do_prompt_ou_None)`` — o objeto (só
    presente quando veio do Langfuse) é associado a cada geração via
    ``update_current_generation(prompt=...)`` em `enviar_mensagem` (NUNCA via
    ``config["metadata"]``: ver comentário lá — isso quebra a serialização
    do checkpoint no Mongo).
    """
    local_text = _PROMPT_PATH.read_text(encoding="utf-8")
    if _langfuse_client is None:
        return local_text, None

    try:
        prompt_obj = _langfuse_client.get_prompt(
            settings.langfuse_prompt_name,
            fallback=local_text,
            fetch_timeout_seconds=10,
        )
        return prompt_obj.compile(), prompt_obj
    except Exception:
        logger.exception("Falha ao buscar prompt do Langfuse — usando prompt local")
        return local_text, None


_SYSTEM_PROMPT, _LANGFUSE_PROMPT_OBJ = _load_system_prompt()

if settings.groq_api_key:
    try:
        _primary = init_chat_model(
            settings.groq_model_primary,
            model_provider="groq",
            api_key=settings.groq_api_key,
            temperature=0.2,
        )
        _fallbacks = [
            init_chat_model(
                nome, model_provider="groq", api_key=settings.groq_api_key, temperature=0.2
            )
            for nome in settings.groq_model_fallbacks_list
        ]
        _middleware = [ModelFallbackMiddleware(*_fallbacks)] if _fallbacks else []

        # Checkpointer do LangGraph pra memória multi-turn. MongoDBSaver usa
        # um pymongo.MongoClient SÍNCRONO (não o AsyncMongoClient de
        # app/db/mongo.py — são classes diferentes, não dá pra compartilhar);
        # os métodos assíncronos que o agente usa (aget_tuple/aput/...) fazem
        # bridge internamente via threadpool. Coleções dedicadas pra não
        # colidir com o resto do banco; db_name explícito porque o default da
        # lib é outro banco ("checkpointing_db").
        _sync_client = MongoClient(settings.mongo_uri)
        _checkpointer = MongoDBSaver(
            _sync_client,
            db_name=settings.mongo_db_name,
            checkpoint_collection_name="agente_checkpoints",
            writes_collection_name="agente_checkpoint_writes",
            ttl=60 * 60 * 24 * 7,  # 7 dias, em segundos (TTL de índice do Mongo)
        )

        AGENT = create_agent(
            model=_primary,
            tools=TOOLS,
            system_prompt=_SYSTEM_PROMPT,
            middleware=_middleware,
            checkpointer=_checkpointer,
        )
    except Exception:
        # não derruba a API se o Groq/checkpointer estiver mal configurado —
        # AGENT fica None, o router responde 404 (mesmo padrão dos outros
        # toggles do projeto).
        logger.exception("Falha ao montar o agente (Groq) — feature ficará indisponível")
        AGENT = None
else:
    logger.info("GROQ_API_KEY não configurada — aba Agente ficará indisponível (404)")


async def _enviar_mensagem_raw(mensagem: str, *, thread_id: str) -> str:
    """Envia uma mensagem ao agente e devolve o texto da resposta final.

    Nunca levanta exceção — falhas (rate limit do Groq, timeout, erro de
    rede) viram uma resposta textual amigável, pra UI não precisar de
    tratamento de erro especial pra esse endpoint.
    """
    assert AGENT is not None, "enviar_mensagem chamado sem o agente montado"

    if _langfuse_client is not None and _LANGFUSE_PROMPT_OBJ is not None:
        try:
            _langfuse_client.update_current_generation(prompt=_LANGFUSE_PROMPT_OBJ)
        except Exception:
            logger.exception("Falha ao associar prompt ao trace do Langfuse")

    config: dict = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": _RECURSION_LIMIT,
    }
    if _langfuse_handler is not None:
        config["callbacks"] = [_langfuse_handler]
        # thread_id é uma string simples — ao contrário do TextPromptClient
        # do bug acima, é sempre serializável via msgpack, então não corre o
        # mesmo risco de quebrar o checkpoint. Agrupa os traces dessa
        # conversa como uma "session" no dashboard do Langfuse (mesma noção
        # de "uma conversa" que o checkpointer já usa pra memória).
        config["metadata"] = {"langfuse_session_id": thread_id}

    try:
        resultado = await asyncio.wait_for(
            AGENT.ainvoke({"messages": [{"role": "user", "content": mensagem}]}, config=config),
            timeout=_TIMEOUT_SECONDS,
        )
        return resultado["messages"][-1].content
    except Exception:
        logger.exception("Falha ao invocar o agente")
        return _MENSAGEM_ERRO


if _langfuse_handler is not None:
    # @observe() abre o span/trace que dá contexto pro
    # update_current_generation() acima conseguir associar o prompt — sem
    # isso não haveria "geração ativa" pra atualizar. Só decora de verdade
    # quando o Langfuse está configurado (senão o SDK loga um aviso de
    # "client initialized without public_key" a cada chamada à toa).
    from langfuse import observe

    enviar_mensagem = observe(name="agente-mensagem", as_type="generation")(_enviar_mensagem_raw)
else:
    enviar_mensagem = _enviar_mensagem_raw


def close() -> None:
    """Fecha o client síncrono do checkpointer — chamado no shutdown da app."""
    if _sync_client is not None:
        _sync_client.close()
