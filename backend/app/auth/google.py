"""Validação do id_token do Google Identity Services.

O frontend obtém um ``id_token`` via Google Identity Services e envia pro
backend. Aqui validamos a assinatura contra as chaves públicas do Google e
extraímos ``email`` + ``email_verified`` + ``name``.
"""
from __future__ import annotations

from dataclasses import dataclass

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.config import settings


@dataclass
class GoogleIdentity:
    email: str
    email_verified: bool
    nome: str | None


class GoogleTokenError(Exception):
    """id_token inválido, expirado ou com audience errada."""


def verify_google_id_token(token: str) -> GoogleIdentity:
    """Valida o id_token e retorna a identidade do usuário.

    Levanta ``GoogleTokenError`` se o token for inválido. A verificação de
    audience (``google_client_id``) só é aplicada quando o client id está
    configurado — em dev sem OAuth configurado, use o dev-login.
    """
    if not settings.google_client_id:
        raise GoogleTokenError(
            "GOOGLE_CLIENT_ID não configurado no backend; use o dev-login em "
            "desenvolvimento ou configure o OAuth do Google."
        )

    try:
        claims = google_id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            settings.google_client_id,
        )
    except ValueError as exc:  # assinatura/audience/expiração inválidas
        raise GoogleTokenError(str(exc)) from exc

    email = claims.get("email")
    if not email:
        raise GoogleTokenError("Token do Google sem e-mail")

    return GoogleIdentity(
        email=email.lower(),
        email_verified=bool(claims.get("email_verified", False)),
        nome=claims.get("name"),
    )
