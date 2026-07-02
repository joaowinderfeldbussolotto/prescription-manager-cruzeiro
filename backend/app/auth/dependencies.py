"""Dependencies de autorização do FastAPI.

- ``get_current_user`` decodifica o cookie de sessão e RE-BUSCA o usuário no
  banco a cada requisição. Isso garante que setar ``ativo = false`` revoga o
  acesso imediatamente, mesmo com sessão ainda válida (SPEC).
- ``require_role`` nasce parametrizável por role pra suportar rotas admin
  futuras (gerenciar allowlist) sem refatorar depois.
"""
from __future__ import annotations

import jwt
from fastapi import Depends, HTTPException, Request, status

from app.auth.session import decode_session_token
from app.db.mongo import get_db
from app.db.serialization import doc_to_api, is_valid_object_id, to_object_id
from app.config import settings

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Não autenticado",
)


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get(settings.cookie_name)
    if not token:
        raise _UNAUTHORIZED

    try:
        payload = decode_session_token(token)
    except jwt.PyJWTError as exc:
        raise _UNAUTHORIZED from exc

    user_id = payload.get("sub")
    if not user_id or not is_valid_object_id(user_id):
        raise _UNAUTHORIZED

    db = get_db()
    doc = await db.usuarios.find_one({"_id": to_object_id(user_id)})
    if doc is None or not doc.get("ativo", False):
        # usuário removido da allowlist ou desativado -> revoga acesso
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão inválida ou acesso revogado",
        )

    return doc_to_api(doc)


def require_role(*roles: str):
    """Retorna uma dependency que exige que o usuário tenha um dos ``roles``."""

    async def _dependency(user: dict = Depends(get_current_user)) -> dict:
        if roles and user.get("role") not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissão insuficiente",
            )
        return user

    return _dependency
