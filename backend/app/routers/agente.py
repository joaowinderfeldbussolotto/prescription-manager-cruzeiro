"""Rotas do Agente (todas exigem sessão válida).

O "cérebro" que interpreta a mensagem é um agente LangChain real (Groq,
tools sobre o banco — ver `app/agent/`). Este router só faz a ponte HTTP:
autentica, checa o toggle de feature e repassa a mensagem.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.agent import service as agent_service
from app.auth.dependencies import get_current_user
from app.config import settings
from app.schemas.agente import AgenteRequest, AgenteResponse

router = APIRouter(prefix="/agente", tags=["agente"])


@router.post("/mensagem", response_model=AgenteResponse)
async def enviar_mensagem(
    payload: AgenteRequest, user: dict = Depends(get_current_user)
) -> AgenteResponse:
    if not settings.agente_enabled or agent_service.AGENT is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Não disponível")

    resposta = await agent_service.enviar_mensagem(payload.mensagem, thread_id=user["id"])
    return AgenteResponse(resposta=resposta)
