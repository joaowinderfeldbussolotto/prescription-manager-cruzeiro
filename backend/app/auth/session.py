"""Sessão própria da aplicação: JWT emitido em cookie httpOnly.

Depois de validar o login (Google ou dev), emitimos nossa própria sessão —
o frontend nunca guarda o id_token do Google, só recebe o cookie de sessão.
"""
from __future__ import annotations

from datetime import timedelta

import jwt

from app.config import settings
from app.db.serialization import utcnow


def create_session_token(*, user_id: str, email: str, role: str) -> str:
    now = utcnow()
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expires_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_session_token(token: str) -> dict:
    """Decodifica e valida o JWT. Levanta ``jwt.PyJWTError`` se inválido."""
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
    )


def set_session_cookie(response, token: str) -> None:
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain,
        max_age=settings.jwt_expires_minutes * 60,
        path="/",
    )


def clear_session_cookie(response) -> None:
    response.delete_cookie(
        key=settings.cookie_name,
        domain=settings.cookie_domain,
        path="/",
    )
