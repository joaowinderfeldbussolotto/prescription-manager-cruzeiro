"""Testes do endpoint de extração (mock) de dados de receita.

Usa ``app.dependency_overrides`` pra simular usuário autenticado (bypassa
cookie/Mongo) e monkeypatch pra isolar o storage (sem MinIO real).

Gotcha: `receitas.py` faz `from app.storage import get_object_bytes` — o
monkeypatch precisa mirar `app.routers.receitas.get_object_bytes` (o nome já
importado no módulo do router), não `app.storage.get_object_bytes` (não
teria efeito nenhum sobre o que o router chama).
"""
from fastapi.testclient import TestClient

import app.routers.receitas as receitas_router
from app.auth.dependencies import get_current_user
from app.config import settings
from app.main import app
from app.storage import ObjectNotFoundError, StorageError

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


def test_extracao_happy_path(monkeypatch):
    _authenticate()
    try:
        monkeypatch.setattr(receitas_router, "get_object_bytes", lambda key: b"fake-bytes")
        r = client.post("/api/receitas/extracao-ia", json={"imagem_key": "receitas/abc.jpg"})
        assert r.status_code == 200
        body = r.json()
        assert body["mock"] is True
        assert body["aviso"]
        assert body["campos"]["od_esferico"] == -2.25
    finally:
        _clear_auth_override()


def test_extracao_imagem_inexistente_404(monkeypatch):
    _authenticate()
    try:
        def _raise(key):
            raise ObjectNotFoundError(key)

        monkeypatch.setattr(receitas_router, "get_object_bytes", _raise)
        r = client.post("/api/receitas/extracao-ia", json={"imagem_key": "receitas/nao-existe.jpg"})
        assert r.status_code == 404
    finally:
        _clear_auth_override()


def test_extracao_falha_storage_500_sem_vazar_detalhe(monkeypatch):
    _authenticate()
    try:
        def _raise(key):
            raise StorageError("detalhe interno sensível")

        monkeypatch.setattr(receitas_router, "get_object_bytes", _raise)
        r = client.post("/api/receitas/extracao-ia", json={"imagem_key": "receitas/x.jpg"})
        assert r.status_code == 500
        assert "detalhe interno sensível" not in r.json()["detail"]
    finally:
        _clear_auth_override()


def test_extracao_toggle_desligado_404(monkeypatch):
    _authenticate()
    try:
        monkeypatch.setattr(settings, "extracao_ia_enabled", False)
        r = client.post("/api/receitas/extracao-ia", json={"imagem_key": "receitas/x.jpg"})
        assert r.status_code == 404
    finally:
        _clear_auth_override()


def test_extracao_sem_sessao_401():
    # nenhum dependency_override — cai no get_current_user real (sem cookie)
    r = client.post("/api/receitas/extracao-ia", json={"imagem_key": "x"})
    assert r.status_code == 401
