"""Rotas do Agente (todas exigem sessão válida).

A interpretação da mensagem é mock (`app/schemas/agente.py` — correspondência
exata contra o catálogo fixo de sugestões do frontend). As TOOLS que a
interpretação aciona abaixo são reais: batem no banco de verdade via
`app/models/cliente.py`, os mesmos repositórios usados por `routers/clientes.py`.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import get_current_user
from app.config import settings
from app.db.mongo import get_db
from app.models import cliente as cliente_repo
from app.schemas.agente import (
    AgenteAcao,
    AgenteLink,
    AgenteRequest,
    AgenteResponse,
    interpretar_mensagem,
)
from app.schemas.cliente import ClienteCreate

router = APIRouter(prefix="/agente", tags=["agente"], dependencies=[Depends(get_current_user)])

_AVISO_MOCK = (
    "Interpretação simulada (sem IA real) — a frase precisa bater com uma das "
    "sugestões. As ações no banco (cadastro, edição, busca) são reais."
)


def _preview_cliente(c: dict) -> dict:
    return {"id": c["id"], "nome": c["nome"], "telefone": c.get("telefone")}


def _link_cliente(c: dict) -> AgenteLink:
    return AgenteLink(label=f"Ver {c['nome']}", href=f"/clientes/{c['id']}")


async def _buscar_clientes(db, termo: str, limit: int = 10) -> list[dict]:
    items, _total = await cliente_repo.list_paginated(db, busca=termo, page=1, limit=limit)
    return items


@router.post("/mensagem", response_model=AgenteResponse)
async def enviar_mensagem(payload: AgenteRequest) -> AgenteResponse:
    if not settings.agente_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Não disponível")

    cenario = interpretar_mensagem(payload.mensagem)
    if cenario is None:
        return AgenteResponse(
            resposta="Ainda não sei responder a essa mensagem (mock) — escolha uma das sugestões abaixo.",
            mock=True,
            aviso=_AVISO_MOCK,
        )

    intent = cenario["intent"]
    argumentos = cenario["argumentos"]
    db = get_db()

    if intent == "cadastrar_cliente":
        dados = ClienteCreate(**argumentos).model_dump()
        criado = await cliente_repo.create(db, dados)
        return AgenteResponse(
            resposta=f"Pronto! Cadastrei {criado['nome']}.",
            acoes=[
                AgenteAcao(
                    tool="cadastrar_cliente",
                    argumentos=argumentos,
                    resultado=_preview_cliente(criado),
                )
            ],
            links=[_link_cliente(criado)],
            mock=True,
            aviso=_AVISO_MOCK,
        )

    if intent == "editar_cliente":
        encontrados = await _buscar_clientes(db, argumentos["busca"], limit=5)
        if not encontrados:
            return AgenteResponse(
                resposta=f"Não encontrei nenhum cliente chamado \"{argumentos['busca']}\".",
                mock=True,
                aviso=_AVISO_MOCK,
            )
        if len(encontrados) > 1:
            return AgenteResponse(
                resposta=f"Encontrei {len(encontrados)} clientes chamados \"{argumentos['busca']}\" — qual deles?",
                links=[_link_cliente(c) for c in encontrados],
                mock=True,
                aviso=_AVISO_MOCK,
            )
        alvo = encontrados[0]
        atualizado = await cliente_repo.update(db, alvo["id"], {"telefone": argumentos["telefone"]})
        return AgenteResponse(
            resposta=f"Telefone de {atualizado['nome']} atualizado para {atualizado['telefone']}.",
            acoes=[
                AgenteAcao(
                    tool="editar_cliente",
                    argumentos=argumentos,
                    resultado=_preview_cliente(atualizado),
                )
            ],
            links=[_link_cliente(atualizado)],
            mock=True,
            aviso=_AVISO_MOCK,
        )

    if intent == "buscar_cliente":
        encontrados = await _buscar_clientes(db, argumentos["busca"], limit=10)
        acao = AgenteAcao(
            tool="buscar_cliente",
            argumentos=argumentos,
            resultado={"total": len(encontrados)},
        )
        if not encontrados:
            return AgenteResponse(
                resposta=f"Não encontrei nenhum cliente chamado \"{argumentos['busca']}\".",
                acoes=[acao],
                mock=True,
                aviso=_AVISO_MOCK,
            )
        if len(encontrados) == 1:
            c = encontrados[0]
            texto = (
                f"Aqui está o histórico de receitas de {c['nome']}:"
                if argumentos.get("foco") == "receitas"
                else f"Encontrei {c['nome']}:"
            )
            return AgenteResponse(
                resposta=texto,
                acoes=[acao],
                links=[_link_cliente(c)],
                mock=True,
                aviso=_AVISO_MOCK,
            )
        return AgenteResponse(
            resposta=f"Encontrei {len(encontrados)} clientes chamados \"{argumentos['busca']}\" — qual deles?",
            acoes=[acao],
            links=[_link_cliente(c) for c in encontrados],
            mock=True,
            aviso=_AVISO_MOCK,
        )

    if intent == "preparar_receita":
        encontrados = await _buscar_clientes(db, argumentos["busca"], limit=5)
        if not encontrados:
            return AgenteResponse(
                resposta=f"Não encontrei nenhum cliente chamado \"{argumentos['busca']}\".",
                mock=True,
                aviso=_AVISO_MOCK,
            )
        if len(encontrados) > 1:
            return AgenteResponse(
                resposta=f"Encontrei {len(encontrados)} clientes chamados \"{argumentos['busca']}\" — qual deles?",
                links=[_link_cliente(c) for c in encontrados],
                mock=True,
                aviso=_AVISO_MOCK,
            )
        alvo = encontrados[0]
        return AgenteResponse(
            resposta=(
                f"Abrindo uma nova receita para {alvo['nome']}. A imagem da receita é "
                "obrigatória — anexe-a no formulário para salvar."
            ),
            acoes=[
                AgenteAcao(
                    tool="preparar_receita",
                    argumentos=argumentos,
                    resultado=_preview_cliente(alvo),
                )
            ],
            links=[AgenteLink(label=f"Nova receita para {alvo['nome']}", href=f"/clientes/{alvo['id']}/receitas/nova")],
            mock=True,
            aviso=_AVISO_MOCK,
        )

    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Intent não tratado")
