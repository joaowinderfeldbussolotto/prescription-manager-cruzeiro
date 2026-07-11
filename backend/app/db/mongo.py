"""Conexão assíncrona com o MongoDB e criação de índices.

Usamos o driver async nativo do PyMongo (``AsyncMongoClient``, disponível a
partir do PyMongo 4.9), que substitui o antigo Motor.

> Nota de migração (SPEC): MongoDB → DynamoDB NÃO é drop-in. As queries aqui
> usam filtros livres (``$regex`` na busca por nome/telefone, filtros por
> intervalo de data no dashboard). Em DynamoDB isso exigiria redesenho de
> modelagem (GSIs, chaves compostas). Está documentado como decisão consciente
> no README.
"""
from __future__ import annotations

import logging

from pymongo import ASCENDING, AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from app.config import settings

logger = logging.getLogger(__name__)

_client: AsyncMongoClient | None = None
_db: AsyncDatabase | None = None


async def connect() -> None:
    """Abre a conexão e garante os índices. Chamado no startup do app."""
    global _client, _db
    _client = AsyncMongoClient(settings.mongo_uri, tz_aware=True)
    _db = _client[settings.mongo_db_name]
    await _ensure_indexes(_db)
    logger.info("Conectado ao MongoDB db=%s", settings.mongo_db_name)


async def close() -> None:
    global _client, _db
    if _client is not None:
        await _client.close()
    _client = None
    _db = None


def get_db() -> AsyncDatabase:
    if _db is None:
        raise RuntimeError("MongoDB não inicializado. Chame connect() no startup.")
    return _db


async def _ensure_indexes(db: AsyncDatabase) -> None:
    # usuarios: email é a chave da allowlist -> índice único
    await db.usuarios.create_index([("email", ASCENDING)], unique=True)

    # clientes: busca por nome/telefone; filtramos deletados nas listagens
    await db.clientes.create_index([("nome", ASCENDING)])
    await db.clientes.create_index([("telefone", ASCENDING)])
    await db.clientes.create_index([("deletado", ASCENDING)])

    # receitas: listar por cliente e ordenar/filtrar por validade
    await db.receitas.create_index([("cliente_id", ASCENDING)])
    await db.receitas.create_index([("validade", ASCENDING)])
