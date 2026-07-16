"""Testes do router de Acompanhamento (todos exigem sessão válida).

Listagem é sempre por RESPONSÁVEL — usuario_id vem do usuário autenticado,
nunca de um parâmetro que o client possa forjar. `mark_done`/`list_by_responsavel`
são monkeypatchados (sem Mongo real neste processo de teste — integração
roda via Docker Compose).
"""
from __future__ import annotations

import pytest

import app.routers.acompanhamentos as acompanhamentos_router
from app.auth.dependencies import get_current_user
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

FAKE_USER = {
    "id": "507f1f77bcf86cd799439011",
    "email": "atendente@teste.com",
    "nome": "Teste",
    "role": "atendente",
    "ativo": True,
}

_ITEM = {
    "id": "507f1f77bcf86cd799439099",
    "cliente_id": "c1",
    "cliente_nome": "Maria Souza",
    "usuario_id": FAKE_USER["id"],
    "usuario_nome": "Teste",
    "data_agendada": "2026-03-01",
    "tipo": "ligar",
    "descricao": "oferecer desconto",
    "concluido": False,
    "criado_em": "2026-01-01T00:00:00Z",
}


def _authenticate():
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER


def _clear_auth_override():
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture(autouse=True)
def _fake_db(monkeypatch):
    # A rota chama get_db() antes de repassar pro repo (que também é
    # monkeypatchado nos testes abaixo e ignora o valor) — sem isso o
    # get_db() real levantaria "MongoDB não inicializado".
    monkeypatch.setattr(acompanhamentos_router, "get_db", lambda: object())


def test_listar_sem_sessao_401():
    assert client.get("/api/acompanhamentos").status_code == 401


def test_concluir_sem_sessao_401():
    assert client.put("/api/acompanhamentos/507f1f77bcf86cd799439099/concluir").status_code == 401


def test_listar_usa_usuario_id_do_usuario_logado(monkeypatch):
    _authenticate()
    try:
        chamadas = []

        async def fake_list(db, usuario_id, *, filtro, page, limit):
            chamadas.append((usuario_id, filtro, page, limit))
            return [], 0

        monkeypatch.setattr(
            acompanhamentos_router.acompanhamento_repo, "list_by_responsavel", fake_list
        )

        r = client.get("/api/acompanhamentos")
        assert r.status_code == 200
        assert r.json() == {"items": [], "total": 0, "page": 1, "limit": 20}
        # usuario_id vem do usuário AUTENTICADO — não é (nem pode ser) um
        # parâmetro de query que o client controla.
        assert chamadas == [(FAKE_USER["id"], "pendentes", 1, 20)]
    finally:
        _clear_auth_override()


def test_listar_com_filtro_e_paginacao(monkeypatch):
    _authenticate()
    try:
        async def fake_list(db, usuario_id, *, filtro, page, limit):
            assert filtro == "concluido"
            assert page == 2
            assert limit == 5
            return [_ITEM], 1

        monkeypatch.setattr(
            acompanhamentos_router.acompanhamento_repo, "list_by_responsavel", fake_list
        )

        r = client.get(
            "/api/acompanhamentos", params={"filtro": "concluido", "page": 2, "limit": 5}
        )
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["items"][0]["cliente_nome"] == "Maria Souza"
    finally:
        _clear_auth_override()


def test_listar_filtro_invalido_422():
    _authenticate()
    try:
        r = client.get("/api/acompanhamentos", params={"filtro": "invalido"})
        assert r.status_code == 422
    finally:
        _clear_auth_override()


def test_concluir_sucesso(monkeypatch):
    _authenticate()
    try:
        async def fake_mark_done(db, acompanhamento_id, usuario_id):
            assert acompanhamento_id == _ITEM["id"]
            assert usuario_id == FAKE_USER["id"]
            return {**_ITEM, "concluido": True}

        monkeypatch.setattr(acompanhamentos_router.acompanhamento_repo, "mark_done", fake_mark_done)

        r = client.put(f"/api/acompanhamentos/{_ITEM['id']}/concluir")
        assert r.status_code == 200
        assert r.json()["concluido"] is True
    finally:
        _clear_auth_override()


def test_concluir_nao_encontrado_404(monkeypatch):
    """`mark_done` devolve None tanto quando o id não existe quanto quando
    pertence a OUTRO usuario_id — dos dois jeitos, 404 (nunca vaza que o
    acompanhamento existe mas é de outro atendente)."""
    _authenticate()
    try:
        async def fake_mark_done(db, acompanhamento_id, usuario_id):
            return None

        monkeypatch.setattr(acompanhamentos_router.acompanhamento_repo, "mark_done", fake_mark_done)

        r = client.put(f"/api/acompanhamentos/{_ITEM['id']}/concluir")
        assert r.status_code == 404
    finally:
        _clear_auth_override()


def test_concluir_id_invalido_404():
    _authenticate()
    try:
        r = client.put("/api/acompanhamentos/id-invalido/concluir")
        assert r.status_code == 404
    finally:
        _clear_auth_override()
