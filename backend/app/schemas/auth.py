"""Schemas de autenticação."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class GoogleLoginRequest(BaseModel):
    id_token: str = Field(..., description="id_token do Google Identity Services")


class DevLoginRequest(BaseModel):
    """Login de desenvolvimento (sem OAuth). Só funciona se DEV_AUTH_ENABLED."""

    email: EmailStr


class UserPublic(BaseModel):
    """Dados básicos do usuário retornados após login e em /auth/me."""

    id: str
    email: EmailStr
    nome: str | None = None
    role: str
    ativo: bool = True
    ultimo_login: datetime | None = None
