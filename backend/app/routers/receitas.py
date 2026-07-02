"""Rotas de Receita (todas exigem sessão válida).

Paths seguem o SPEC: criação/listagem aninhadas sob o cliente, e
detalhe/edição/remoção diretas por id da receita.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import get_current_user
from app.db.mongo import get_db
from app.db.serialization import is_valid_object_id
from datetime import date, datetime

from app.models import cliente as cliente_repo
from app.models import receita as receita_repo
from app.schemas.receita import ReceitaCreate, ReceitaPublic, ReceitaUpdate, add_12_months
from app.storage import delete_object, generate_view_url

router = APIRouter(tags=["receitas"], dependencies=[Depends(get_current_user)])


def _as_date(value: date | datetime | None) -> date | None:
    """Normaliza para ``date`` — o Mongo devolve ``datetime``, o request ``date``."""
    if isinstance(value, datetime):
        return value.date()
    return value


def _to_public(doc: dict) -> ReceitaPublic:
    """Monta o schema de resposta, anexando a presigned URL da imagem."""
    imagem_url = None
    if doc.get("imagem_key"):
        imagem_url = generate_view_url(doc["imagem_key"])
    return ReceitaPublic(**doc, imagem_url=imagem_url)


def _ensure_valid_id(entity_id: str, label: str) -> None:
    if not is_valid_object_id(entity_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{label} não encontrado")


async def _get_receita_or_404(db, receita_id: str) -> dict:
    _ensure_valid_id(receita_id, "Receita")
    doc = await receita_repo.get(db, receita_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receita não encontrada")
    return doc


@router.post(
    "/clientes/{cliente_id}/receitas",
    response_model=ReceitaPublic,
    status_code=status.HTTP_201_CREATED,
)
async def criar_receita(cliente_id: str, payload: ReceitaCreate) -> ReceitaPublic:
    _ensure_valid_id(cliente_id, "Cliente")
    db = get_db()
    cliente = await cliente_repo.get(db, cliente_id)
    if cliente is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado")

    created = await receita_repo.create(db, cliente_id, payload.model_dump())
    return _to_public(created)


@router.get("/clientes/{cliente_id}/receitas", response_model=list[ReceitaPublic])
async def listar_receitas_do_cliente(cliente_id: str) -> list[ReceitaPublic]:
    _ensure_valid_id(cliente_id, "Cliente")
    db = get_db()
    receitas = await receita_repo.list_by_cliente(db, cliente_id)
    return [_to_public(r) for r in receitas]


@router.get("/receitas/{receita_id}", response_model=ReceitaPublic)
async def obter_receita(receita_id: str) -> ReceitaPublic:
    db = get_db()
    doc = await _get_receita_or_404(db, receita_id)
    return _to_public(doc)


@router.put("/receitas/{receita_id}", response_model=ReceitaPublic)
async def atualizar_receita(receita_id: str, payload: ReceitaUpdate) -> ReceitaPublic:
    db = get_db()
    existing = await _get_receita_or_404(db, receita_id)

    changes = payload.model_dump(exclude_unset=True)
    merged = {**existing, **changes}

    # regra de negócio reavaliada sobre o documento mesclado
    if merged.get("od_esferico") is None and merged.get("oe_esferico") is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Pelo menos um grau esférico (OD ou OE) deve ser informado",
        )

    # normaliza para date (existing vem como datetime do Mongo, changes como date)
    emissao = _as_date(merged.get("data_emissao"))
    validade = _as_date(merged.get("validade"))
    # se a validade foi limpa, recompõe o default (+12 meses) — nunca fica nula
    if validade is None and emissao is not None:
        validade = add_12_months(emissao)
        changes["validade"] = validade
    if validade and emissao and validade < emissao:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="validade não pode ser anterior à data de emissão",
        )

    # se a imagem foi trocada, remove a antiga do storage (best effort)
    old_key = existing.get("imagem_key")
    new_key = merged.get("imagem_key")
    updated = await receita_repo.update(db, receita_id, changes)
    if old_key and old_key != new_key:
        delete_object(old_key)
    return _to_public(updated)


@router.delete("/receitas/{receita_id}", status_code=status.HTTP_200_OK)
async def remover_receita(receita_id: str) -> dict:
    db = get_db()
    await _get_receita_or_404(db, receita_id)
    removed = await receita_repo.delete(db, receita_id)
    if removed and removed.get("imagem_key"):
        delete_object(removed["imagem_key"])
    return {"id": receita_id, "deleted": True}
