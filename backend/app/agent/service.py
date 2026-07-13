"""Monta e expõe o agente real (LangChain + Groq) usado pelo chat "Agente".

Construído uma única vez, na importação deste módulo (mesmo padrão de
`settings = get_settings()` em `app/config.py`) — SE `GROQ_API_KEY` estiver
configurada; caso contrário `AGENT` fica `None` e o router trata isso como
feature indisponível (mesmo padrão dos outros toggles do projeto: 404).
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
_SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")

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


async def enviar_mensagem(mensagem: str, *, thread_id: str) -> str:
    """Envia uma mensagem ao agente e devolve o texto da resposta final.

    Nunca levanta exceção — falhas (rate limit do Groq, timeout, erro de
    rede) viram uma resposta textual amigável, pra UI não precisar de
    tratamento de erro especial pra esse endpoint.
    """
    assert AGENT is not None, "enviar_mensagem chamado sem o agente montado"
    try:
        resultado = await asyncio.wait_for(
            AGENT.ainvoke(
                {"messages": [{"role": "user", "content": mensagem}]},
                config={
                    "configurable": {"thread_id": thread_id},
                    "recursion_limit": _RECURSION_LIMIT,
                },
            ),
            timeout=_TIMEOUT_SECONDS,
        )
        return resultado["messages"][-1].content
    except Exception:
        logger.exception("Falha ao invocar o agente")
        return _MENSAGEM_ERRO


def close() -> None:
    """Fecha o client síncrono do checkpointer — chamado no shutdown da app."""
    if _sync_client is not None:
        _sync_client.close()
