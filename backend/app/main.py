"""Ponto de entrada da API FastAPI.

No startup:
- conecta no MongoDB e garante índices
- garante que o bucket do MinIO existe (MinIO não cria bucket sozinho)
- semeia o admin inicial na allowlist (SEED_ADMIN_EMAIL), se configurado
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent import service as agent_service
from app.config import settings
from app.db import mongo
from app.models import usuario as usuario_repo
from app.routers import acompanhamentos, agente, auth, clientes, dashboard, receitas, uploads
from app.storage import ensure_bucket

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await mongo.connect()
    try:
        ensure_bucket()
    except Exception:  # não derruba a API se o storage estiver indisponível
        logger.exception("Falha ao garantir o bucket do storage no startup")

    if settings.seed_admin_email:
        await usuario_repo.ensure_seed_admin(mongo.get_db(), settings.seed_admin_email)

    logger.info("%s pronta (env=%s)", settings.app_name, settings.environment)
    yield
    agent_service.close()
    await mongo.close()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    summary="Cadastro de clientes e receitas ópticas",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,  # necessário pro cookie de sessão
    allow_methods=["*"],
    allow_headers=["*"],
)

# Todas as rotas de negócio ficam sob o prefixo /api (proxy amigável).
for r in (
    auth.router,
    clientes.router,
    receitas.router,
    uploads.router,
    dashboard.router,
    agente.router,
    acompanhamentos.router,
):
    app.include_router(r, prefix=settings.api_prefix)


@app.get("/health", tags=["infra"])
@app.get(f"{settings.api_prefix}/health", tags=["infra"])
async def health() -> dict:
    return {"status": "ok", "app": settings.app_name}
