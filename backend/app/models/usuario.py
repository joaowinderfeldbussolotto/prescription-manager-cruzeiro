"""Persistência de Usuario (allowlist).

Cadastro é manual nesta fase (SPEC): usuários entram direto no banco ou via
seed. Não há autoregistro.
"""
from __future__ import annotations

import logging

from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from app.db.serialization import doc_to_api, to_object_id, utcnow

logger = logging.getLogger(__name__)

VALID_ROLES = {"admin", "atendente"}


async def get_by_email(db: AsyncDatabase, email: str) -> dict | None:
    return await db.usuarios.find_one({"email": email.lower()})


async def get_by_id(db: AsyncDatabase, user_id: str) -> dict | None:
    return await db.usuarios.find_one({"_id": to_object_id(user_id)})


async def touch_last_login(db: AsyncDatabase, user_id: str, nome: str | None = None) -> dict:
    """Atualiza ultimo_login e, se ainda não houver nome, grava o do perfil."""
    update: dict = {"ultimo_login": utcnow()}
    doc = await db.usuarios.find_one({"_id": to_object_id(user_id)})
    if nome and doc is not None and not doc.get("nome"):
        update["nome"] = nome
    result = await db.usuarios.find_one_and_update(
        {"_id": to_object_id(user_id)},
        {"$set": update},
        return_document=ReturnDocument.AFTER,
    )
    return doc_to_api(result)


async def ensure_seed_admin(db: AsyncDatabase, email: str) -> None:
    """Cria (idempotente) um admin inicial na allowlist a partir do env.

    Sem isso, ninguém consegue logar na primeira subida — o cadastro é manual.
    """
    email = email.lower().strip()
    if not email:
        return
    try:
        await db.usuarios.insert_one(
            {
                "email": email,
                "nome": None,
                "ativo": True,
                "role": "admin",
                "data_criacao": utcnow(),
                "ultimo_login": None,
            }
        )
        logger.info("Usuário admin semeado na allowlist: %s", email)
    except DuplicateKeyError:
        logger.info("Admin seed já existe na allowlist: %s", email)
