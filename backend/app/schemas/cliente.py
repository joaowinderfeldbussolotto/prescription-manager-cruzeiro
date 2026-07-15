"""Schemas de Cliente."""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, EmailStr, Field, field_validator

# Aceita CPF com ou sem pontuação. Validação de FORMATO apenas (não valida
# dígito verificador) — conforme SPEC.
_CPF_RE = re.compile(r"^\d{3}\.?\d{3}\.?\d{3}-?\d{2}$")


def _validate_cpf_format(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if value == "":
        return None
    if not _CPF_RE.match(value):
        raise ValueError("CPF em formato inválido (esperado 000.000.000-00)")
    return value


class Acompanhamento(BaseModel):
    """Follow-up/lembrete ligado ao cliente."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    data_agendada: date
    tipo: Literal["ligar", "email", "sms", "visita", "outro"]
    descricao: str = Field(..., min_length=1, max_length=500)
    criado_em: datetime = Field(default_factory=datetime.now)
    concluido: bool = False


class ClienteBase(BaseModel):
    nome: str = Field(..., min_length=1, max_length=200)
    cpf: str | None = Field(default=None, description="Formato validado, sem dígito verificador")
    telefone: str = Field(..., min_length=1, max_length=40)
    email: EmailStr | None = None
    data_nascimento: date | None = None
    endereco: str | None = Field(default=None, max_length=500)
    acompanhamentos: list[Acompanhamento] = Field(default_factory=list)

    @field_validator("cpf")
    @classmethod
    def _cpf(cls, v: str | None) -> str | None:
        return _validate_cpf_format(v)

    @field_validator("nome", "telefone")
    @classmethod
    def _strip_required(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Campo obrigatório não pode ser vazio")
        return v


class ClienteCreate(ClienteBase):
    pass


class ClienteUpdate(BaseModel):
    """Update parcial — todos os campos opcionais."""

    nome: str | None = Field(default=None, min_length=1, max_length=200)
    cpf: str | None = None
    telefone: str | None = Field(default=None, min_length=1, max_length=40)
    email: EmailStr | None = None
    data_nascimento: date | None = None
    endereco: str | None = Field(default=None, max_length=500)

    @field_validator("cpf")
    @classmethod
    def _cpf(cls, v: str | None) -> str | None:
        return _validate_cpf_format(v)


class ClientePublic(ClienteBase):
    id: str
    data_cadastro: datetime


class ClienteResumo(BaseModel):
    """Resumo usado nas listagens."""

    id: str
    nome: str
    telefone: str
    email: EmailStr | None = None
    data_cadastro: datetime
    total_receitas: int = 0


class ReceitaResumo(BaseModel):
    """Resumo de receita para o histórico dentro do detalhe do cliente."""

    id: str
    data_emissao: date
    validade: date
    medico_nome: str | None = None
    tem_imagem: bool = False


class ClienteDetalhe(ClientePublic):
    """Detalhe do cliente + histórico resumido de receitas."""

    receitas: list[ReceitaResumo] = Field(default_factory=list)
