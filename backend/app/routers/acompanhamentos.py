"""Rotas de Acompanhamento (todas exigem sessão válida).

A listagem é sempre por RESPONSÁVEL — o usuário logado que criou o
acompanhamento (diretamente ou em nome de um cliente), nunca por cliente.
Ver docstring de `app.schemas.acompanhamento` pro motivo da collection
própria. Criação acontece só via tool do Agente (`agendar_acompanhamento`) —
aqui só listamos e marcamos como concluído.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.dependencies import get_current_user
from app.db.mongo import get_db
from app.db.serialization import is_valid_object_id
from app.models import acompanhamento as acompanhamento_repo
from app.schemas.acompanhamento import AcompanhamentoPublic
from app.schemas.common import Page

router = APIRouter(
    prefix="/acompanhamentos",
    tags=["acompanhamentos"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=Page[AcompanhamentoPublic])
async def listar_acompanhamentos(
    filtro: Literal["pendentes", "concluido", "todos"] = Query(default="pendentes"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(get_current_user),
) -> Page[AcompanhamentoPublic]:
    db = get_db()
    items, total = await acompanhamento_repo.list_by_responsavel(
        db, user["id"], filtro=filtro, page=page, limit=limit
    )
    return Page[AcompanhamentoPublic](
        items=[AcompanhamentoPublic(**i) for i in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.put("/{acompanhamento_id}/concluir", response_model=AcompanhamentoPublic)
async def concluir_acompanhamento(
    acompanhamento_id: str, user: dict = Depends(get_current_user)
) -> AcompanhamentoPublic:
    if not is_valid_object_id(acompanhamento_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Acompanhamento não encontrado")

    db = get_db()
    # mark_done já escopa por usuario_id — um atendente não conclui
    # acompanhamento de outro nem adivinhando o id.
    atualizado = await acompanhamento_repo.mark_done(db, acompanhamento_id, user["id"])
    if atualizado is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Acompanhamento não encontrado")
    return AcompanhamentoPublic(**atualizado)
