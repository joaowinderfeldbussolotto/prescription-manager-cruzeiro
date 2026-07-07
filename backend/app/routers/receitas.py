"""Rotas de Receita (todas exigem sessão válida).

Paths seguem o SPEC: criação/listagem aninhadas sob o cliente,
detalhe/edição/remoção diretas por id da receita, e uma ação por
`imagem_key` (extração mock, sem cliente/receita associada ainda).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool

from app.auth.dependencies import get_current_user
from app.config import settings
from app.db.mongo import get_db
from app.db.serialization import is_valid_object_id
from datetime import date, datetime

from app.models import cliente as cliente_repo
from app.models import receita as receita_repo
from app.schemas.extracao import (
    ExtracaoReceitaRequest,
    ExtracaoReceitaResponse,
    mock_extrair_campos_receita,
)
from app.schemas.receita import ReceitaCreate, ReceitaPublic, ReceitaUpdate, add_12_months
from app.storage import (
    ObjectNotFoundError,
    StorageError,
    delete_object,
    generate_view_url,
    get_object_bytes,
)

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


# Registrada ANTES das rotas /receitas/{receita_id}: o Starlette resolve
# ambiguidade entre rota estática e dinâmica pela ORDEM de registro. Hoje não
# há colisão real (esta é POST; as rotas /receitas/{receita_id} são
# GET/PUT/DELETE), mas evita que um futuro POST /receitas/{receita_id}
# capture "extracao-ia" como se fosse um receita_id.
@router.post("/receitas/extracao-ia", response_model=ExtracaoReceitaResponse)
async def extrair_dados_receita(payload: ExtracaoReceitaRequest) -> ExtracaoReceitaResponse:
    """Extrai (mock) campos sugeridos a partir da imagem já enviada ao storage.

    MOCK: substituir por chamada de IA real (ver app/schemas/extracao.py).
    Nunca persiste nada — só sugere campos pro frontend pré-preencher o
    formulário; o atendente sempre revisa antes de salvar.
    """
    if not settings.extracao_ia_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Não disponível")

    try:
        image_bytes = await run_in_threadpool(get_object_bytes, payload.imagem_key)
    except ObjectNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Imagem não encontrada no storage — envie a imagem antes de extrair os dados",
        ) from None
    except StorageError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Não foi possível acessar o storage de imagens no momento. Tente novamente.",
        ) from None

    campos = mock_extrair_campos_receita(image_bytes, payload.imagem_key)
    return ExtracaoReceitaResponse(
        campos=campos,
        mock=True,
        aviso=(
            "Sugestão gerada por mock — não é leitura real da imagem. "
            "Revise todos os campos antes de salvar."
        ),
    )


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

    # normaliza para date (existing vem como datetime do Mongo, changes como date)
    emissao = _as_date(merged.get("data_emissao"))
    validade = _as_date(merged.get("validade"))
    # emissão nunca fica nula (default = hoje)
    if emissao is None:
        emissao = date.today()
        changes["data_emissao"] = emissao
    # se a validade foi limpa, recompõe o default (+12 meses) — nunca fica nula
    if validade is None:
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
