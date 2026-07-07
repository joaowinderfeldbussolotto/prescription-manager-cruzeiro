"""Schemas de extração (mock) de dados de receita a partir da imagem.

Fase atual: mock determinístico (ver SPEC.md — nenhuma integração real de
IA nesta fase). O contrato de request/response já é desenhado pra
sobreviver à troca por uma chamada real a um modelo de visão — só a
implementação de ``mock_extrair_campos_receita`` muda, o schema não.
"""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class ExtracaoReceitaRequest(BaseModel):
    imagem_key: str = Field(..., description="Chave do objeto já enviado ao storage (MinIO/S3)")


class ExtracaoReceitaCampos(BaseModel):
    """Subconjunto "extraível da imagem" de ReceitaBase — mesmos nomes de
    campo, propositalmente, pra o merge no frontend ser 1:1 sem tradução."""

    data_emissao: date | None = None
    medico_nome: str | None = None
    medico_crm: str | None = None
    od_esferico: float | None = None
    od_cilindrico: float | None = None
    od_eixo: int | None = None
    od_adicao: float | None = None
    oe_esferico: float | None = None
    oe_cilindrico: float | None = None
    oe_eixo: int | None = None
    oe_adicao: float | None = None
    dp: float | None = None
    dp_longe: float | None = None
    dp_perto: float | None = None


class ExtracaoReceitaResponse(BaseModel):
    campos: ExtracaoReceitaCampos
    mock: bool = Field(
        default=True,
        description="true enquanto a extração for simulada; passa a false quando plugada a uma IA real (contrato não muda)",
    )
    aviso: str | None = Field(
        default=None,
        description="Mensagem a exibir no frontend quando mock=true; null/ausente quando for extração real",
    )


def mock_extrair_campos_receita(image_bytes: bytes, imagem_key: str) -> ExtracaoReceitaCampos:
    """Gera campos de EXEMPLO plausíveis pra pré-preencher o formulário.

    MOCK: substituir por chamada de IA real (enviar ``image_bytes`` — e,
    futuramente, tratar ``imagem_key`` pra diferenciar PDF de imagem — pro
    modelo com visão e parsear a resposta no formato de
    ExtracaoReceitaCampos). Os bytes/key não são usados hoje; ficam na
    assinatura só pra a troca futura não exigir mudar a chamada, só o corpo
    desta função.
    """
    return ExtracaoReceitaCampos(
        data_emissao=date.today(),
        medico_nome="Dr. Ricardo Alves",
        medico_crm="CRM-SP 123456",
        od_esferico=-2.25,
        od_cilindrico=-0.75,
        od_eixo=90,
        od_adicao=1.50,
        oe_esferico=-2.00,
        oe_cilindrico=-0.50,
        oe_eixo=85,
        oe_adicao=1.50,
        dp=32.0,
        dp_longe=32.0,
        dp_perto=30.0,
    )
