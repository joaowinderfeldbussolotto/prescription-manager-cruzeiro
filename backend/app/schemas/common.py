"""Schemas utilitários compartilhados."""
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Envelope de paginação usado nas listagens."""

    items: list[T]
    total: int
    page: int
    limit: int

    @property
    def pages(self) -> int:  # pragma: no cover - conveniência
        return (self.total + self.limit - 1) // self.limit if self.limit else 0


class MessageResponse(BaseModel):
    message: str


class DeleteResponse(BaseModel):
    id: str
    deleted: bool
    soft: bool = Field(
        default=False,
        description="true quando foi soft delete (havia receitas vinculadas)",
    )
