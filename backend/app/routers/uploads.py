"""Rota de upload via presigned URL (exige sessão válida)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import get_current_user
from app.schemas.upload import PresignedUrlRequest, PresignedUrlResponse
from app.storage import allowed_content_type, generate_upload_url

router = APIRouter(
    prefix="/uploads",
    tags=["uploads"],
    dependencies=[Depends(get_current_user)],
)


@router.post("/presigned-url", response_model=PresignedUrlResponse)
async def presigned_url(payload: PresignedUrlRequest) -> PresignedUrlResponse:
    if not allowed_content_type(payload.content_type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"content_type não suportado: {payload.content_type}",
        )
    url, key = generate_upload_url(payload.content_type)
    return PresignedUrlResponse(upload_url=url, key=key)
