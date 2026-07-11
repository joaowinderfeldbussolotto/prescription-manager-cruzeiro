"""Smoke tests de HTTP com o TestClient.

Não sobem lifespan (sem `with`), então o MongoDB não é acessado — cobrimos os
caminhos que resolvem ANTES de qualquer chamada ao banco: health, guardas de
autenticação (401 sem cookie) e validação de payload (422). Os testes de
integração com banco real rodam via Docker Compose.
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_me_sem_cookie_401():
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_clientes_exige_sessao():
    assert client.get("/api/clientes").status_code == 401
    assert client.post("/api/clientes", json={"nome": "X", "telefone": "1"}).status_code == 401


def test_receitas_e_uploads_exigem_sessao():
    assert client.get("/api/clientes/abc/receitas").status_code == 401
    assert client.get("/api/receitas/abc").status_code == 401
    assert (
        client.post("/api/uploads/presigned-url", json={"content_type": "image/png"}).status_code
        == 401
    )
    assert (
        client.post("/api/receitas/extracao-ia", json={"imagem_key": "x"}).status_code == 401
    )
    assert client.get("/api/dashboard").status_code == 401
    assert client.post("/api/agente/mensagem", json={"mensagem": "x"}).status_code == 401


def test_dev_login_email_invalido_422():
    # validação do Pydantic falha antes de tocar o banco
    r = client.post("/api/auth/dev-login", json={"email": "nao-e-email"})
    assert r.status_code == 422


def test_openapi_lista_todas_as_rotas():
    paths = client.get("/openapi.json").json()["paths"]
    esperadas = {
        "/api/auth/google",
        "/api/auth/dev-login",
        "/api/auth/me",
        "/api/auth/logout",
        "/api/clientes",
        "/api/clientes/{cliente_id}",
        "/api/clientes/{cliente_id}/receitas",
        "/api/receitas/{receita_id}",
        "/api/receitas/extracao-ia",
        "/api/uploads/presigned-url",
        "/api/dashboard",
        "/api/agente/mensagem",
    }
    assert esperadas.issubset(paths.keys())
