"""Rotas de autenticação."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.auth.dependencies import get_current_user
from app.auth.google import GoogleTokenError, verify_google_id_token
from app.auth.session import (
    clear_session_cookie,
    create_session_token,
    set_session_cookie,
)
from app.config import settings
from app.db.mongo import get_db
from app.models import usuario as usuario_repo
from app.schemas.auth import DevLoginRequest, GoogleLoginRequest, UserPublic

router = APIRouter(prefix="/auth", tags=["auth"])


async def _login_email(response: Response, email: str, nome: str | None) -> UserPublic:
    """Fluxo comum pós-verificação de identidade: valida allowlist e emite sessão."""
    db = get_db()
    user = await usuario_repo.get_by_email(db, email)
    if user is None or not user.get("ativo", False):
        # 403 explícito e com mensagem clara (o frontend trata isso de forma
        # amigável — não é um erro genérico de servidor).
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email não autorizado",
        )

    updated = await usuario_repo.touch_last_login(db, str(user["_id"]), nome=nome)
    token = create_session_token(
        user_id=updated["id"], email=updated["email"], role=updated["role"]
    )
    set_session_cookie(response, token)
    return UserPublic(**updated)


@router.post("/google", response_model=UserPublic)
async def login_google(payload: GoogleLoginRequest, response: Response) -> UserPublic:
    try:
        identity = verify_google_id_token(payload.id_token)
    except GoogleTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token do Google inválido",
        ) from exc

    if not identity.email_verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail do Google não verificado",
        )

    return await _login_email(response, identity.email, identity.nome)


@router.post("/dev-login", response_model=UserPublic)
async def login_dev(payload: DevLoginRequest, response: Response) -> UserPublic:
    """Login de desenvolvimento SEM OAuth. Desabilite em produção.

    Não valida senha nem token — apenas confere se o e-mail está na allowlist
    e está ativo. Serve só pra facilitar o dev local.
    """
    if not settings.dev_auth_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Não disponível")
    return await _login_email(response, payload.email.lower(), None)


@router.get("/me", response_model=UserPublic)
async def me(user: dict = Depends(get_current_user)) -> UserPublic:
    return UserPublic(**user)


@router.post("/logout")
async def logout(response: Response) -> dict:
    clear_session_cookie(response)
    return {"message": "Sessão encerrada"}
