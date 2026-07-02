"""Rotas de Cliente (todas exigem sessão válida)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.dependencies import get_current_user
from app.db.mongo import get_db
from app.db.serialization import is_valid_object_id
from app.models import cliente as cliente_repo
from app.models import receita as receita_repo
from app.schemas.cliente import (
    ClienteCreate,
    ClienteDetalhe,
    ClientePublic,
    ClienteResumo,
    ClienteUpdate,
    ReceitaResumo,
)
from app.schemas.common import DeleteResponse, Page

router = APIRouter(
    prefix="/clientes",
    tags=["clientes"],
    dependencies=[Depends(get_current_user)],
)


def _ensure_valid_id(cliente_id: str) -> None:
    if not is_valid_object_id(cliente_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado")


@router.post("", response_model=ClientePublic, status_code=status.HTTP_201_CREATED)
async def criar_cliente(payload: ClienteCreate) -> ClientePublic:
    db = get_db()
    created = await cliente_repo.create(db, payload.model_dump())
    return ClientePublic(**created)


@router.get("", response_model=Page[ClienteResumo])
async def listar_clientes(
    busca: str | None = Query(default=None, description="Busca por nome ou telefone"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> Page[ClienteResumo]:
    db = get_db()
    items, total = await cliente_repo.list_paginated(db, busca=busca, page=page, limit=limit)
    return Page[ClienteResumo](
        items=[ClienteResumo(**i) for i in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/{cliente_id}", response_model=ClienteDetalhe)
async def obter_cliente(cliente_id: str) -> ClienteDetalhe:
    _ensure_valid_id(cliente_id)
    db = get_db()
    cliente = await cliente_repo.get(db, cliente_id)
    if cliente is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado")

    receitas = await receita_repo.list_by_cliente(db, cliente_id)
    resumo = [
        ReceitaResumo(
            id=r["id"],
            data_emissao=r["data_emissao"],
            validade=r["validade"],
            medico_nome=r.get("medico_nome"),
            tem_imagem=bool(r.get("imagem_key")),
        )
        for r in receitas
    ]
    return ClienteDetalhe(**cliente, receitas=resumo)


@router.put("/{cliente_id}", response_model=ClientePublic)
async def atualizar_cliente(cliente_id: str, payload: ClienteUpdate) -> ClientePublic:
    _ensure_valid_id(cliente_id)
    db = get_db()
    data = payload.model_dump(exclude_unset=True)
    updated = await cliente_repo.update(db, cliente_id, data)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado")
    return ClientePublic(**updated)


@router.delete("/{cliente_id}", response_model=DeleteResponse)
async def remover_cliente(cliente_id: str) -> DeleteResponse:
    _ensure_valid_id(cliente_id)
    db = get_db()
    removed, soft = await cliente_repo.delete(db, cliente_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado")
    return DeleteResponse(id=cliente_id, deleted=True, soft=soft)
