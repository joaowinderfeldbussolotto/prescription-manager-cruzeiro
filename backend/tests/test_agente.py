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
        assert chamadas == [("Cadastra a Maria Souza", FAKE_USER["id"])]
    finally:
        _clear_auth_override()


def test_agente_mensagem_vazia_422():
    _authenticate()
    try:
        r = client.post("/api/agente/mensagem", json={"mensagem": ""})
        assert r.status_code == 422
    finally:
        _clear_auth_override()


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
