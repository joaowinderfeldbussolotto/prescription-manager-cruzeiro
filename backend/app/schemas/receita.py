"""Schemas de Receita óptica."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator


def add_12_months(d: date) -> date:
    """Retorna a data + 12 meses (validade padrão da receita).

    12 meses == 1 ano. Trata o caso 29/02 caindo em ano não bissexto.
    """
    try:
        return d.replace(year=d.year + 1)
    except ValueError:  # 29/02 -> 28/02
        return d.replace(year=d.year + 1, day=28)


class OlhoGrau(BaseModel):
    """Grau de um olho (usado só na documentação/estrutura; a persistência é
    flat como no SPEC)."""

    esferico: float | None = None
    cilindrico: float | None = None
    eixo: int | None = Field(default=None, ge=0, le=180)
    adicao: float | None = None


# Faixas generosas só pra barrar erro grosseiro de digitação — não são regra
# clínica rígida.
_ESF = dict(ge=-40, le=40)
_CIL = dict(ge=-40, le=40)
_ADD = dict(ge=0, le=10)
_DP = dict(ge=10, le=120)


class ReceitaBase(BaseModel):
    data_emissao: date
    validade: date | None = Field(
        default=None,
        description="Default = data_emissao + 12 meses (calculado no backend se omitido)",
    )
    medico_nome: str | None = Field(default=None, max_length=200)
    medico_crm: str | None = Field(default=None, max_length=40)

    # Olho direito (OD)
    od_esferico: float | None = Field(default=None, **_ESF)
    od_cilindrico: float | None = Field(default=None, **_CIL)
    od_eixo: int | None = Field(default=None, ge=0, le=180)
    od_adicao: float | None = Field(default=None, **_ADD)

    # Olho esquerdo (OE)
    oe_esferico: float | None = Field(default=None, **_ESF)
    oe_cilindrico: float | None = Field(default=None, **_CIL)
    oe_eixo: int | None = Field(default=None, ge=0, le=180)
    oe_adicao: float | None = Field(default=None, **_ADD)

    # Distância pupilar
    dp: float | None = Field(default=None, **_DP)
    dp_longe: float | None = Field(default=None, **_DP)
    dp_perto: float | None = Field(default=None, **_DP)

    observacoes: str | None = Field(default=None, max_length=2000)
    imagem_key: str | None = Field(default=None, description="Chave do objeto no MinIO/S3")


def _at_least_one_esferico(od: float | None, oe: float | None) -> bool:
    return od is not None or oe is not None


class ReceitaCreate(ReceitaBase):
    @model_validator(mode="after")
    def _defaults_and_rules(self) -> "ReceitaCreate":
        # validade padrão = emissão + 12 meses (editável)
        if self.validade is None:
            self.validade = add_12_months(self.data_emissao)
        if self.validade < self.data_emissao:
            raise ValueError("validade não pode ser anterior à data de emissão")
        # regra de negócio: pelo menos um esférico preenchido
        if not _at_least_one_esferico(self.od_esferico, self.oe_esferico):
            raise ValueError(
                "Pelo menos um grau esférico (OD ou OE) deve ser informado"
            )
        return self


class ReceitaUpdate(BaseModel):
    """Update parcial. A regra 'pelo menos um esférico' é reavaliada no router
    sobre o documento já mesclado."""

    data_emissao: date | None = None
    validade: date | None = None
    medico_nome: str | None = Field(default=None, max_length=200)
    medico_crm: str | None = Field(default=None, max_length=40)
    od_esferico: float | None = Field(default=None, **_ESF)
    od_cilindrico: float | None = Field(default=None, **_CIL)
    od_eixo: int | None = Field(default=None, ge=0, le=180)
    od_adicao: float | None = Field(default=None, **_ADD)
    oe_esferico: float | None = Field(default=None, **_ESF)
    oe_cilindrico: float | None = Field(default=None, **_CIL)
    oe_eixo: int | None = Field(default=None, ge=0, le=180)
    oe_adicao: float | None = Field(default=None, **_ADD)
    dp: float | None = Field(default=None, **_DP)
    dp_longe: float | None = Field(default=None, **_DP)
    dp_perto: float | None = Field(default=None, **_DP)
    observacoes: str | None = Field(default=None, max_length=2000)
    imagem_key: str | None = None


class ReceitaPublic(ReceitaBase):
    id: str
    cliente_id: str
    validade: date  # sempre presente após criação
    data_cadastro: datetime
    imagem_url: str | None = Field(
        default=None,
        description="Presigned URL de leitura da imagem (quando houver imagem_key)",
    )
