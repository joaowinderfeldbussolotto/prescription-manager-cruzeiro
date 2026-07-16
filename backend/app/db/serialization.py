"""Helpers de (de)serialização entre documentos BSON e a API.

- ``_id`` (ObjectId) é exposto como ``id`` (string) na API — evita vazar o
  formato interno do Mongo pro frontend (SPEC).
- BSON não tem tipo "date puro", só ``datetime``. Guardamos campos de data
  como ``datetime`` à meia-noite UTC e o Pydantic faz a coerção para ``date``
  na resposta.
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any

from bson import ObjectId


def is_valid_object_id(value: str) -> bool:
    return ObjectId.is_valid(value)


def to_object_id(value: str) -> ObjectId:
    return ObjectId(value)


def doc_to_api(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    """Converte um documento Mongo em dict pronto pra virar schema de resposta.

    Renomeia ``_id`` -> ``id`` (string). Não mexe nos demais campos; a coerção
    de ``datetime`` -> ``date`` fica a cargo dos response models do Pydantic.
    """
    if doc is None:
        return None
    out = dict(doc)
    _id = out.pop("_id", None)
    if _id is not None:
        out["id"] = str(_id)
    return out


def date_to_datetime(value: date | datetime | None) -> datetime | None:
    """Normaliza um ``date``/``datetime`` para ``datetime`` tz-aware (UTC).

    Necessário porque o driver do Mongo só aceita ``datetime``.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    # date puro -> meia-noite UTC
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def as_date(value: date | datetime | None) -> date | None:
    """Inverso de `date_to_datetime`: normaliza para ``date`` puro.

    O Mongo sempre devolve ``datetime`` (ver `date_to_datetime`); código que
    compara essas datas com um ``date`` puro (do request, ou `date.today()`)
    precisa normalizar os dois lados primeiro — misturar `datetime` e `date`
    numa subtração levanta `TypeError`.
    """
    if isinstance(value, datetime):
        return value.date()
    return value


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
