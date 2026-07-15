"""Persistência de Cliente."""
from __future__ import annotations

import re

from pymongo import ASCENDING, ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase

from app.db.serialization import doc_to_api, date_to_datetime, to_object_id, utcnow


class ClienteDuplicadoError(Exception):
    """Levantada ao tentar cadastrar/editar um cliente com telefone que já
    pertence a outro cliente ativo (não soft-deletado)."""


def _base_filter() -> dict:
    # exclui soft-deletados das listagens/consultas
    return {"deletado": {"$ne": True}}


async def _buscar_por_telefone(
    db: AsyncDatabase, telefone: str, *, excluir_id: str | None = None
) -> dict | None:
    query = {"telefone": telefone, **_base_filter()}
    if excluir_id is not None:
        query["_id"] = {"$ne": to_object_id(excluir_id)}
    return await db.clientes.find_one(query)


async def create(db: AsyncDatabase, data: dict) -> dict:
    doc = dict(data)
    telefone = doc.get("telefone")
    if telefone:
        existente = await _buscar_por_telefone(db, telefone)
        if existente is not None:
            raise ClienteDuplicadoError(
                f"Já existe um cliente cadastrado com o telefone {telefone}: {existente['nome']}."
            )
    if "data_nascimento" in doc:
        doc["data_nascimento"] = date_to_datetime(doc["data_nascimento"])
    doc["data_cadastro"] = utcnow()
    doc["deletado"] = False
    result = await db.clientes.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc_to_api(doc)


async def get(db: AsyncDatabase, cliente_id: str) -> dict | None:
    doc = await db.clientes.find_one({"_id": to_object_id(cliente_id), **_base_filter()})
    return doc_to_api(doc)


async def list_paginated(
    db: AsyncDatabase, *, busca: str | None, page: int, limit: int
) -> tuple[list[dict], int]:
    query = _base_filter()
    if busca:
        rx = re.escape(busca.strip())
        query = {
            **query,
            "$or": [
                {"nome": {"$regex": rx, "$options": "i"}},
                {"telefone": {"$regex": rx, "$options": "i"}},
            ],
        }

    total = await db.clientes.count_documents(query)
    cursor = (
        db.clientes.find(query)
        .sort("nome", ASCENDING)
        .skip((page - 1) * limit)
        .limit(limit)
    )
    docs = await cursor.to_list(length=limit)

    # conta receitas por cliente da página em uma única agregação
    ids = [str(d["_id"]) for d in docs]
    counts: dict[str, int] = {}
    if ids:
        pipeline = [
            {"$match": {"cliente_id": {"$in": ids}}},
            {"$group": {"_id": "$cliente_id", "n": {"$sum": 1}}},
        ]
        async for row in await db.receitas.aggregate(pipeline):
            counts[row["_id"]] = row["n"]

    items = []
    for d in docs:
        api = doc_to_api(d)
        api["total_receitas"] = counts.get(api["id"], 0)
        items.append(api)
    return items, total


async def update(db: AsyncDatabase, cliente_id: str, data: dict) -> dict | None:
    doc = dict(data)
    telefone = doc.get("telefone")
    if telefone:
        existente = await _buscar_por_telefone(db, telefone, excluir_id=cliente_id)
        if existente is not None:
            raise ClienteDuplicadoError(
                f"Já existe outro cliente cadastrado com o telefone {telefone}: {existente['nome']}."
            )
    if "data_nascimento" in doc and doc["data_nascimento"] is not None:
        doc["data_nascimento"] = date_to_datetime(doc["data_nascimento"])
    if not doc:
        return await get(db, cliente_id)
    result = await db.clientes.find_one_and_update(
        {"_id": to_object_id(cliente_id), **_base_filter()},
        {"$set": doc},
        return_document=ReturnDocument.AFTER,
    )
    return doc_to_api(result)


async def count_receitas(db: AsyncDatabase, cliente_id: str) -> int:
    return await db.receitas.count_documents({"cliente_id": cliente_id})


async def delete(db: AsyncDatabase, cliente_id: str) -> tuple[bool, bool]:
    """Remove o cliente.

    Se houver receitas vinculadas, faz SOFT delete (marca ``deletado=True``)
    pra preservar o histórico (SPEC). Caso contrário, hard delete.

    Retorna ``(removido, foi_soft)``.
    """
    oid = to_object_id(cliente_id)
    existing = await db.clientes.find_one({"_id": oid, **_base_filter()})
    if existing is None:
        return False, False

    receitas = await count_receitas(db, cliente_id)
    if receitas > 0:
        await db.clientes.update_one(
            {"_id": oid},
            {"$set": {"deletado": True, "data_delecao": utcnow()}},
        )
        return True, True

    await db.clientes.delete_one({"_id": oid})
    return True, False


async def add_acompanhamento(db: AsyncDatabase, cliente_id: str, acompanhamento: dict) -> bool:
    """Adiciona um acompanhamento à lista do cliente."""
    result = await db.clientes.update_one(
        {"_id": to_object_id(cliente_id), **_base_filter()},
        {
            "$push": {"acompanhamentos": acompanhamento},
            "$set": {"data_atualizado": utcnow()},
        },
    )
    return result.modified_count > 0


async def mark_acompanhamento_done(
    db: AsyncDatabase, cliente_id: str, acompanhamento_id: str
) -> bool:
    """Marca um acompanhamento como concluído."""
    result = await db.clientes.update_one(
        {"_id": to_object_id(cliente_id), "acompanhamentos.id": acompanhamento_id},
        {"$set": {"acompanhamentos.$.concluido": True}},
    )
    return result.modified_count > 0
