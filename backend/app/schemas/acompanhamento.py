"""Schemas de Acompanhamento (follow-up/lembrete criado pelo Agente).

Collection própria (não embutida em Cliente): a listagem é sempre por
RESPONSÁVEL — o atendente (usuário logado) que criou o acompanhamento, não
o cliente a quem ele se refere. Um `$unwind` num array embutido em cada
cliente pra achar "todos os acompanhamentos do atendente X" seria uma
agregação cara sobre a collection inteira de clientes; com campos `cliente_id`
e `usuario_id` no topo do documento, a query é um filtro simples e indexável.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class AcompanhamentoBase(BaseModel):
    cliente_id: str
    # nome do cliente denormalizado — evita um join/lookup só pra exibir a
    # listagem (que é por responsável, cruzando vários clientes de uma vez).
    cliente_nome: str
    usuario_id: str
    usuario_nome: str
    data_agendada: date
    tipo: Literal["ligar", "email", "sms", "visita", "outro"]
    descricao: str = Field(..., min_length=1, max_length=500)
    concluido: bool = False


class AcompanhamentoCreate(AcompanhamentoBase):
    pass


class AcompanhamentoPublic(AcompanhamentoBase):
    id: str
    criado_em: datetime
