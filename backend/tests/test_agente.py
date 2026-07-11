"""Testes do endpoint do Agente (mock).

A interpretação da mensagem é por correspondência exata (`CENARIOS_MOCK` em
`app/schemas/agente.py`) — os testes usam as próprias chaves desse dicionário
como payload, pra não duplicar (e não deixar dessincronizar) o texto exato das
mensagens.

As TOOLS que o router aciona são monkeypatchadas em `app.routers.agente.
cliente_repo` (mesmo módulo usado por `routers/clientes.py`) — não batemos
num Mongo real, só isolamos o roteamento intent -> tool.
"""
from fastapi.testclient import TestClient

import app.routers.agente as agente_router
from app.auth.dependencies import get_current_user
from app.config import settings
from app.main import app
from app.schemas.agente import CENARIOS_MOCK

client = TestClient(app)

FAKE_USER = {
    "id": "507f1f77bcf86cd799439011",
    "email": "atendente@teste.com",
    "nome": "Teste",
    "role": "atendente",
    "ativo": True,
}

MSG_CADASTRAR = "Cadastra a cliente Maria Souza, CPF 111.222.333-44, telefone (48) 99911-2233, nascida em 12/04/1990"
MSG_EDITAR = "Atualiza o telefone da Maria Souza para (48) 3333-0000"
MSG_BUSCAR = "Busca a cliente Maria"
MSG_PREPARAR_RECEITA = "Prepara uma receita para a Maria Souza"


def _authenticate():
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER


def _clear_auth_override():
    app.dependency_overrides.pop(get_current_user, None)


def _fake_get_db(monkeypatch):
    # `agente.py` chama `get_db()` diretamente (não é Depends do FastAPI);
    # nos testes não há Mongo real conectado, então isolamos com um sentinel —
    # as funções de cliente_repo usadas nele são monkeypatchadas em cada
    # teste e ignoram o valor de fato.
    monkeypatch.setattr(agente_router, "get_db", lambda: object())


def test_todas_as_mensagens_de_teste_existem_no_catalogo():
    # garante que os literais usados neste arquivo não dessincronizaram do
    # catálogo real que o frontend também usa como chips de sugestão
    for msg in (MSG_CADASTRAR, MSG_EDITAR, MSG_BUSCAR, MSG_PREPARAR_RECEITA):
        assert msg in CENARIOS_MOCK


def test_agente_sem_sessao_401():
    r = client.post("/api/agente/mensagem", json={"mensagem": MSG_BUSCAR})
    assert r.status_code == 401


def test_agente_toggle_desligado_404(monkeypatch):
    _authenticate()
    try:
        monkeypatch.setattr(settings, "agente_enabled", False)
        r = client.post("/api/agente/mensagem", json={"mensagem": MSG_BUSCAR})
        assert r.status_code == 404
    finally:
        _clear_auth_override()


def test_mensagem_desconhecida_nao_bate_nenhum_cenario():
    _authenticate()
    try:
        r = client.post("/api/agente/mensagem", json={"mensagem": "Isso aqui não está no catálogo"})
        assert r.status_code == 200
        body = r.json()
        assert body["mock"] is True
        assert body["acoes"] == []
        assert body["links"] == []
    finally:
        _clear_auth_override()


def test_cadastrar_cliente_chama_tool_real(monkeypatch):
    _authenticate()
    try:
        _fake_get_db(monkeypatch)
        criado = {"id": "665aaa", "nome": "Maria Souza", "telefone": "(48) 99911-2233"}

        async def fake_create(db, data):
            assert data["nome"] == "Maria Souza"
            assert data["cpf"] == "111.222.333-44"
            return criado

        monkeypatch.setattr(agente_router.cliente_repo, "create", fake_create)
        r = client.post("/api/agente/mensagem", json={"mensagem": MSG_CADASTRAR})
        assert r.status_code == 200
        body = r.json()
        assert body["mock"] is True
        assert body["acoes"][0]["tool"] == "cadastrar_cliente"
        assert body["links"][0]["href"] == "/clientes/665aaa"
    finally:
        _clear_auth_override()


def test_editar_cliente_atualiza_telefone(monkeypatch):
    _authenticate()
    try:
        _fake_get_db(monkeypatch)
        encontrado = {"id": "665bbb", "nome": "Maria Souza", "telefone": "(48) 99911-2233"}
        atualizado = {"id": "665bbb", "nome": "Maria Souza", "telefone": "(48) 3333-0000"}

        async def fake_list_paginated(db, *, busca, page, limit):
            assert busca == "Maria Souza"
            return [encontrado], 1

        async def fake_update(db, cliente_id, data):
            assert cliente_id == "665bbb"
            assert data == {"telefone": "(48) 3333-0000"}
            return atualizado

        monkeypatch.setattr(agente_router.cliente_repo, "list_paginated", fake_list_paginated)
        monkeypatch.setattr(agente_router.cliente_repo, "update", fake_update)
        r = client.post("/api/agente/mensagem", json={"mensagem": MSG_EDITAR})
        assert r.status_code == 200
        body = r.json()
        assert body["acoes"][0]["tool"] == "editar_cliente"
        assert body["links"][0]["href"] == "/clientes/665bbb"
    finally:
        _clear_auth_override()


def test_buscar_cliente_ambiguo_retorna_varios_links(monkeypatch):
    _authenticate()
    try:
        _fake_get_db(monkeypatch)
        encontrados = [
            {"id": "1", "nome": "Maria Souza", "telefone": "x"},
            {"id": "2", "nome": "Maria Oliveira", "telefone": "y"},
        ]

        async def fake_list_paginated(db, *, busca, page, limit):
            return encontrados, len(encontrados)

        monkeypatch.setattr(agente_router.cliente_repo, "list_paginated", fake_list_paginated)
        r = client.post("/api/agente/mensagem", json={"mensagem": MSG_BUSCAR})
        assert r.status_code == 200
        body = r.json()
        assert len(body["links"]) == 2
    finally:
        _clear_auth_override()


def test_buscar_cliente_unico_retorna_um_link(monkeypatch):
    _authenticate()
    try:
        _fake_get_db(monkeypatch)
        encontrado = [{"id": "665ccc", "nome": "Maria Souza", "telefone": "x"}]

        async def fake_list_paginated(db, *, busca, page, limit):
            return encontrado, 1

        monkeypatch.setattr(agente_router.cliente_repo, "list_paginated", fake_list_paginated)
        r = client.post("/api/agente/mensagem", json={"mensagem": MSG_BUSCAR})
        assert r.status_code == 200
        body = r.json()
        assert len(body["links"]) == 1
        assert body["links"][0]["href"] == "/clientes/665ccc"
    finally:
        _clear_auth_override()


def test_buscar_cliente_sem_resultado(monkeypatch):
    _authenticate()
    try:
        _fake_get_db(monkeypatch)
        async def fake_list_paginated(db, *, busca, page, limit):
            return [], 0

        monkeypatch.setattr(agente_router.cliente_repo, "list_paginated", fake_list_paginated)
        r = client.post("/api/agente/mensagem", json={"mensagem": MSG_BUSCAR})
        assert r.status_code == 200
        body = r.json()
        assert body["links"] == []
    finally:
        _clear_auth_override()


def test_preparar_receita_hand_off_para_formulario(monkeypatch):
    _authenticate()
    try:
        _fake_get_db(monkeypatch)
        encontrado = [{"id": "665ddd", "nome": "Maria Souza", "telefone": "x"}]

        async def fake_list_paginated(db, *, busca, page, limit):
            return encontrado, 1

        monkeypatch.setattr(agente_router.cliente_repo, "list_paginated", fake_list_paginated)
        r = client.post("/api/agente/mensagem", json={"mensagem": MSG_PREPARAR_RECEITA})
        assert r.status_code == 200
        body = r.json()
        assert body["links"][0]["href"] == "/clientes/665ddd/receitas/nova"
    finally:
        _clear_auth_override()
