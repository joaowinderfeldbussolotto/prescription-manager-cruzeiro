"""Persistência de Acompanhamento — collection própria, indexada por
`usuario_id` (o responsável). Ver docstring de `app.schemas.acompanhamento`
pro motivo de não ficar embutido em Cliente."""
from __future__ import annotations

from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase

from app.db.serialization import doc_to_api, date_to_datetime, to_object_id, utcnow


def _filtro_status(filtro: str) -> dict:
    if filtro == "pendentes":
        return {"concluido": False}
    if filtro == "concluido":
        return {"concluido": True}
    return {}  # "todos" (ou qualquer outro valor) -> sem filtro de status


async def create(db: AsyncDatabase, data: dict) -> dict:
    doc = dict(data)
    doc["data_agendada"] = date_to_datetime(doc["data_agendada"])
    doc["criado_em"] = utcnow()
    doc.setdefault("concluido", False)
    result = await db.acompanhamentos.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc_to_api(doc)


async def list_by_responsavel(
    db: AsyncDatabase, usuario_id: str, *, filtro: str = "pendentes", page: int = 1, limit: int = 20
) -> tuple[list[dict], int]:
    query = {"usuario_id": usuario_id, **_filtro_status(filtro)}
    total = await db.acompanhamentos.count_documents(query)
    cursor = (
        db.acompanhamentos.find(query)
        .sort("data_agendada", ASCENDING if filtro != "concluido" else DESCENDING)
        .skip((page - 1) * limit)
        .limit(limit)
    )
    docs = await cursor.to_list(length=limit)
    return [doc_to_api(d) for d in docs], total


async def mark_done(db: AsyncDatabase, acompanhamento_id: str, usuario_id: str) -> dict | None:
    """Marca como concluído — escopado ao `usuario_id` (responsável), pra um
    atendente não conseguir concluir o acompanhamento de outro via id
    adivinhado/copiado."""
    result = await db.acompanhamentos.find_one_and_update(
        {"_id": to_object_id(acompanhamento_id), "usuario_id": usuario_id},
        {"$set": {"concluido": True}},
        return_document=ReturnDocument.AFTER,
    )
    return doc_to_api(result)
