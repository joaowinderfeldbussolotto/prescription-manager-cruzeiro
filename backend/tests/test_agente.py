"""Testes do endpoint do Agente (agora um agente LangChain real).

Duas camadas:
1. Testes de ROUTER (401/404/200) via `TestClient`, com `agent_service`
   monkeypatchado — não fazem nenhuma chamada de rede real ao Groq.
2. Um teste de FIAÇÃO que monta um `create_agent` de verdade com as tools e
   o prompt reais do projeto, mas usando um chat model fake (determinístico,
   sem rede) e um checkpointer em memória — pega erro de schema de tool ou
   de prompt ausente/mal formatado sem precisar de GROQ_API_KEY nem de
   Mongo real (a tool ainda roda de verdade; sem Mongo conectado, o
   try/except da tool devolve uma string de erro, exercitando esse caminho).
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from langchain.agents import create_agent
from langchain_core.language_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver

import app.routers.agente as agente_router
from app.agent import service as agent_service
from app.agent.service import _SYSTEM_PROMPT
from app.agent.tools import TOOLS
from app.auth.dependencies import get_current_user
from app.config import settings
from app.main import app

client = TestClient(app)

FAKE_USER = {
    "id": "507f1f77bcf86cd799439011",
    "email": "atendente@teste.com",
    "nome": "Teste",
    "role": "atendente",
    "ativo": True,
}


def _authenticate():
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER


def _clear_auth_override():
    app.dependency_overrides.pop(get_current_user, None)


# --- Router ----------------------------------------------------------------


def test_agente_sem_sessao_401():
    r = client.post("/api/agente/mensagem", json={"mensagem": "oi"})
    assert r.status_code == 401


def test_agente_toggle_desligado_404(monkeypatch):
    _authenticate()
    try:
        monkeypatch.setattr(settings, "agente_enabled", False)
        r = client.post("/api/agente/mensagem", json={"mensagem": "oi"})
        assert r.status_code == 404
    finally:
        _clear_auth_override()


def test_agente_sem_groq_configurado_404(monkeypatch):
    _authenticate()
    try:
        monkeypatch.setattr(agente_router.agent_service, "AGENT", None)
        r = client.post("/api/agente/mensagem", json={"mensagem": "oi"})
        assert r.status_code == 404
    finally:
        _clear_auth_override()


def test_agente_happy_path_chama_o_agente(monkeypatch):
    _authenticate()
    try:
        chamadas = []

        async def fake_enviar_mensagem(mensagem: str, *, thread_id: str) -> str:
            chamadas.append((mensagem, thread_id))
            return "Pronto! Cadastrei a Maria Souza. [Maria Souza](/clientes/665aaa)"

        monkeypatch.setattr(agente_router.agent_service, "AGENT", object())
        monkeypatch.setattr(agente_router.agent_service, "enviar_mensagem", fake_enviar_mensagem)

        r = client.post("/api/agente/mensagem", json={"mensagem": "Cadastra a Maria Souza"})
        assert r.status_code == 200
        body = r.json()
        assert body == {"resposta": "Pronto! Cadastrei a Maria Souza. [Maria Souza](/clientes/665aaa)"}
        # sem session_id no payload -> cai no comportamento antigo (thread fixo por usuário)
        assert chamadas == [("Cadastra a Maria Souza", FAKE_USER["id"])]
    finally:
        _clear_auth_override()


def test_agente_com_session_id_compoe_thread_id(monkeypatch):
    """Com `session_id` (gerado pelo frontend a cada carregamento de página,
    F5 inclusive), o thread_id vira `user_id:session_id` — cada carregamento
    de página ganha sua própria memória/conversa, em vez de um thread fixo
    pra sempre por usuário."""
    _authenticate()
    try:
        chamadas = []

        async def fake_enviar_mensagem(mensagem: str, *, thread_id: str) -> str:
            chamadas.append((mensagem, thread_id))
            return "ok"

        monkeypatch.setattr(agente_router.agent_service, "AGENT", object())
        monkeypatch.setattr(agente_router.agent_service, "enviar_mensagem", fake_enviar_mensagem)

        r = client.post(
            "/api/agente/mensagem",
            json={"mensagem": "oi", "session_id": "abc123"},
        )
        assert r.status_code == 200
        assert chamadas == [("oi", f"{FAKE_USER['id']}:abc123")]
    finally:
        _clear_auth_override()


def test_agente_mensagem_vazia_422():
    _authenticate()
    try:
        r = client.post("/api/agente/mensagem", json={"mensagem": ""})
        assert r.status_code == 422
    finally:
        _clear_auth_override()


def test_prompt_local_sem_langfuse_configurado():
    """Sem LANGFUSE_SECRET_KEY/LANGFUSE_PUBLIC_KEY (default no ambiente de
    teste), o client do Langfuse nem é construído, e o prompt do sistema
    vem do arquivo local — sem chamada de rede."""
    assert agent_service._langfuse_client is None
    texto, prompt_obj = agent_service._load_system_prompt()
    assert prompt_obj is None
    assert texto == agent_service._PROMPT_PATH.read_text(encoding="utf-8")
    assert texto == _SYSTEM_PROMPT


def test_prompt_do_langfuse_nunca_vai_pro_metadata_do_checkpoint(monkeypatch):
    """Regressão: colocar o objeto do prompt do Langfuse (TextPromptClient)
    em `config["metadata"]` quebra a serialização msgpack do checkpoint no
    Mongo assim que o agente tenta salvar (visto em produção: `TypeError:
    Type is not msgpack serializable: TextPromptClient` — o LangGraph
    mescla `config["metadata"]` no CheckpointMetadata persistido pelo
    MongoDBSaver). A associação do prompt precisa ir por
    `update_current_generation(prompt=...)`, nunca pelo `config` do
    `.ainvoke()`."""

    class FakePromptObj:
        """Qualquer classe custom não-primitiva reproduz o bug — não
        precisa ser um TextPromptClient de verdade."""

    class FakeLangfuseClient:
        def __init__(self):
            self.update_current_generation_chamado_com = None

        def update_current_generation(self, *, prompt):
            self.update_current_generation_chamado_com = prompt

    class FakeAgent:
        def __init__(self):
            self.config_recebido = None

        async def ainvoke(self, state, config):
            self.config_recebido = config
            return {"messages": [type("M", (), {"content": "ok"})()]}

    fake_prompt = FakePromptObj()
    fake_client = FakeLangfuseClient()
    fake_agent = FakeAgent()

    monkeypatch.setattr(agent_service, "_LANGFUSE_PROMPT_OBJ", fake_prompt)
    monkeypatch.setattr(agent_service, "_langfuse_client", fake_client)
    monkeypatch.setattr(agent_service, "AGENT", fake_agent)

    import asyncio

    asyncio.run(agent_service._enviar_mensagem_raw("oi", thread_id="t1"))

    assert "metadata" not in fake_agent.config_recebido
    assert fake_client.update_current_generation_chamado_com is fake_prompt


def test_langfuse_session_id_usa_o_thread_id(monkeypatch):
    """`config["metadata"]["langfuse_session_id"]` precisa ser o mesmo
    `thread_id` usado pra memória do checkpointer — agrupa os traces daquela
    conversa como uma "session" no Langfuse. Isso é seguro (string simples,
    sempre serializável via msgpack) mesmo quando `_LANGFUSE_PROMPT_OBJ`
    também está setado (não reintroduz o bug do teste anterior)."""

    class FakePromptObj:
        pass

    class FakeLangfuseClient:
        def update_current_generation(self, *, prompt):
            pass

    class FakeAgent:
        def __init__(self):
            self.config_recebido = None

        async def ainvoke(self, state, config):
            self.config_recebido = config
            return {"messages": [type("M", (), {"content": "ok"})()]}

    fake_agent = FakeAgent()

    monkeypatch.setattr(agent_service, "_LANGFUSE_PROMPT_OBJ", FakePromptObj())
    monkeypatch.setattr(agent_service, "_langfuse_client", FakeLangfuseClient())
    monkeypatch.setattr(agent_service, "_langfuse_handler", object())
    monkeypatch.setattr(agent_service, "AGENT", fake_agent)

    import asyncio

    asyncio.run(agent_service._enviar_mensagem_raw("oi", thread_id="usuario-123"))

    assert fake_agent.config_recebido["metadata"] == {"langfuse_session_id": "usuario-123"}
    # o objeto do prompt continua fora do metadata, mesmo com callbacks/metadata ativos
    assert "langfuse_prompt" not in fake_agent.config_recebido["metadata"]


# --- Fiação (agente real, modelo fake, sem rede/Mongo) ----------------------


class _FakeToolCallingModel(FakeMessagesListChatModel):
    """Fake chat model que sobrescreve `bind_tools` (a base de langchain_core
    levanta NotImplementedError, já que normalmente cada provider real
    traduz o schema da tool pro seu próprio formato de API)."""

    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        return self


def test_fiacao_agente_real_com_modelo_fake():
    """Monta create_agent com as TOOLS e o system_prompt reais do projeto —
    pega erro de schema de tool quebrado ou prompt ausente/mal formatado sem
    precisar de GROQ_API_KEY nem de Mongo real."""
    fake_model = _FakeToolCallingModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "buscar_cliente",
                        "args": {"termo": "Maria"},
                        "id": "call_1",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="Não encontrei ninguém com esse nome."),
        ]
    )

    agent = create_agent(
        model=fake_model,
        tools=TOOLS,
        system_prompt=_SYSTEM_PROMPT,
        checkpointer=MemorySaver(),
    )

    import asyncio

    async def _run():
        return await agent.ainvoke(
            {"messages": [{"role": "user", "content": "busca a Maria"}]},
            config={"configurable": {"thread_id": "wiring-test"}, "recursion_limit": 12},
        )

    resultado = asyncio.run(_run())
    mensagens = resultado["messages"]

    # A tool real rodou (sem Mongo conectado nesse processo de teste, o
    # try/except dela devolveu uma string de erro em vez de derrubar o turno).
    tool_messages = [m for m in mensagens if m.type == "tool"]
    assert len(tool_messages) == 1
    assert "Erro ao buscar cliente" in tool_messages[0].content

    assert mensagens[-1].content == "Não encontrei ninguém com esse nome."
