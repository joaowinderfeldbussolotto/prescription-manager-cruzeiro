"""Persistência de Receita óptica."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from pymongo import DESCENDING, ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase

from app.db.serialization import doc_to_api, date_to_datetime, to_object_id, utcnow

# campos de data que precisam virar datetime pra persistir no Mongo
_DATE_FIELDS = ("data_emissao", "validade")


def _normalize_dates(doc: dict) -> dict:
    for f in _DATE_FIELDS:
        if f in doc and doc[f] is not None:
            doc[f] = date_to_datetime(doc[f])
    return doc


async def create(db: AsyncDatabase, cliente_id: str, data: dict) -> dict:
    doc = _normalize_dates(dict(data))
    doc["cliente_id"] = cliente_id
    doc["data_cadastro"] = utcnow()
    result = await db.receitas.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc_to_api(doc)


async def get(db: AsyncDatabase, receita_id: str) -> dict | None:
    doc = await db.receitas.find_one({"_id": to_object_id(receita_id)})
    return doc_to_api(doc)


async def list_by_cliente(db: AsyncDatabase, cliente_id: str) -> list[dict]:
    # timeline: mais recentes primeiro (por data de emissão)
    cursor = db.receitas.find({"cliente_id": cliente_id}).sort("data_emissao", DESCENDING)
    docs = await cursor.to_list(length=None)
    return [doc_to_api(d) for d in docs]


async def update(db: AsyncDatabase, receita_id: str, data: dict) -> dict | None:
    doc = _normalize_dates(dict(data))
    if not doc:
        return await get(db, receita_id)
    result = await db.receitas.find_one_and_update(
        {"_id": to_object_id(receita_id)},
        {"$set": doc},
        return_document=ReturnDocument.AFTER,
    )
    return doc_to_api(result)


async def delete(db: AsyncDatabase, receita_id: str) -> dict | None:
    """Remove a receita e retorna o documento removido (pra limpar a imagem)."""
    doc = await db.receitas.find_one_and_delete({"_id": to_object_id(receita_id)})
    return doc_to_api(doc)


# --- Dashboard -----------------------------------------------------------

async def count_total_clientes(db: AsyncDatabase) -> int:
    return await db.clientes.count_documents({"deletado": {"$ne": True}})


async def count_receitas_no_mes(db: AsyncDatabase, ref: datetime) -> int:
    inicio = datetime(ref.year, ref.month, 1, tzinfo=ref.tzinfo)
    if ref.month == 12:
        fim = datetime(ref.year + 1, 1, 1, tzinfo=ref.tzinfo)
    else:
        fim = datetime(ref.year, ref.month + 1, 1, tzinfo=ref.tzinfo)
    return await db.receitas.count_documents(
        {"data_cadastro": {"$gte": inicio, "$lt": fim}}
    )


async def count_vencendo_em(db: AsyncDatabase, ref: datetime, dias: int = 30) -> int:
    hoje = date_to_datetime(ref.date())
    limite = hoje + timedelta(days=dias)
    return await db.receitas.count_documents(
        {"validade": {"$gte": hoje, "$lte": limite}}
    )
