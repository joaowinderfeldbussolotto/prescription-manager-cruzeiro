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

    # session_id vem de um carregamento de página do chat (F5 gera um novo)
    # — combinado com o id do usuário autenticado, dá um thread por
    # carregamento em vez de um thread fixo pra sempre por usuário. Sem
    # session_id (client antigo/cache), cai no comportamento anterior.
    thread_id = f"{user['id']}:{payload.session_id}" if payload.session_id else user["id"]
    # usuario_id/nome identificam o RESPONSÁVEL pra tools como
    # agendar_acompanhamento (nunca exposto ao LLM — chega só via
    # RunnableConfig, ver app/agent/service.py e app/agent/tools.py).
    resposta = await agent_service.enviar_mensagem(
        payload.mensagem,
        thread_id=thread_id,
        usuario_id=user["id"],
        usuario_nome=user.get("nome") or user.get("email"),
    )
    return AgenteResponse(resposta=resposta)
