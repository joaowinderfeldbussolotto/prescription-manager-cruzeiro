"""Schemas de upload de imagem."""
from __future__ import annotations

from pydantic import BaseModel, Field


class PresignedUrlRequest(BaseModel):
    content_type: str = Field(..., description="MIME type do arquivo, ex image/jpeg")


class PresignedUrlResponse(BaseModel):
    upload_url: str = Field(..., description="URL de PUT direto no storage")
    key: str = Field(..., description="Chave do objeto — enviar no create/update da receita")
