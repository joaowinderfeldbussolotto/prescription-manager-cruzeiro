"""Schemas do endpoint do Agente.

A interpretação da mensagem agora é feita por um agente LangChain real (ver
`app/agent/service.py`) — este módulo só carrega o contrato HTTP.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class AgenteRequest(BaseModel):
    mensagem: str = Field(..., min_length=1, max_length=2000)
    # Identifica o carregamento de página do chat no frontend (gerado uma
    # vez por mount — um F5 gera um novo). NÃO é a sessão de autenticação
    # (cookie de login) — ver routers/agente.py, onde é combinado com o id
    # do usuário autenticado pra formar o thread_id do agente. Opcional:
    # sem ele, cai no comportamento antigo (thread fixo por usuário).
    session_id: str | None = Field(default=None, max_length=100)


class AgenteResponse(BaseModel):
    resposta: str
