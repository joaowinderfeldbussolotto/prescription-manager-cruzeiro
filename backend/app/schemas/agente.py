"""Schemas do endpoint do Agente.

A interpretação da mensagem agora é feita por um agente LangChain real (ver
`app/agent/service.py`) — este módulo só carrega o contrato HTTP.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class AgenteRequest(BaseModel):
    mensagem: str = Field(..., min_length=1, max_length=2000)


class AgenteResponse(BaseModel):
    resposta: str
