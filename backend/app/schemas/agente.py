"""Schemas do "Agente" (mock) — chat em linguagem natural que cadastra,
edita e busca clientes.

Fase atual: a INTERPRETAÇÃO da mensagem é um lookup por CORRESPONDÊNCIA EXATA
(ver `CENARIOS_MOCK` abaixo — nenhuma integração real de IA nesta fase, ver
SPEC.md). As TOOLS que a interpretação aciona (`app/routers/agente.py`)
são reais: cadastram, editam e buscam clientes de verdade no banco. Quando um
LLM real entrar no lugar do lookup, o contrato de request/response não muda —
só a implementação de `interpretar_mensagem` (equivalente ao que um LLM faria:
produzir intenção + argumentos estruturados de tool a partir do texto).
"""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Interpretação da mensagem: correspondência EXATA, não regex/NLU.
#
# Por que exact match em vez de regex/parsing de intent: nesta fase não existe
# LLM, e o frontend não aceita texto livre — o usuário só pode clicar em uma
# das frases fixas do catálogo de sugestões (`frontend/src/pages/Agente.jsx`,
# `SUGESTOES`). Como o conjunto de mensagens possíveis é finito e conhecido de
# antemão, não há ambiguidade de linguagem natural pra resolver: cada frase do
# catálogo mapeia 1:1 pra uma entrada aqui, com intent e argumentos já
# extraídos manualmente (porque nós escrevemos as duas pontas). Isso elimina
# de vez os edge cases de regex (variações de acentuação, ordem de palavras,
# nomes com apóstrofo etc.) sem esconder a mecânica real do fluxo: a busca, a
# criação e a edição de cliente abaixo continuam batendo no banco de verdade.
#
# Quando o texto livre + LLM real entrarem (fora de escopo agora), esta tabela
# é substituída por uma chamada ao modelo com tool-calling; o formato de saída
# (intent + argumentos) e o restante do pipeline (execução da tool, resposta)
# permanecem os mesmos.
CENARIOS_MOCK: dict[str, dict] = {
    "Cadastra a cliente Maria Souza, CPF 111.222.333-44, telefone (48) 99911-2233, nascida em 12/04/1990": {
        "intent": "cadastrar_cliente",
        "argumentos": {
            "nome": "Maria Souza",
            "cpf": "111.222.333-44",
            "telefone": "(48) 99911-2233",
            "data_nascimento": date(1990, 4, 12),
        },
    },
    "Cadastra a cliente Maria Oliveira, telefone (48) 98822-1100": {
        "intent": "cadastrar_cliente",
        "argumentos": {
            "nome": "Maria Oliveira",
            "telefone": "(48) 98822-1100",
        },
    },
    "Atualiza o telefone da Maria Souza para (48) 3333-0000": {
        "intent": "editar_cliente",
        "argumentos": {
            "busca": "Maria Souza",
            "telefone": "(48) 3333-0000",
        },
    },
    "Busca a cliente Maria": {
        "intent": "buscar_cliente",
        "argumentos": {"busca": "Maria"},
    },
    "Busca as receitas da Maria Souza": {
        "intent": "buscar_cliente",
        "argumentos": {"busca": "Maria Souza", "foco": "receitas"},
    },
    "Prepara uma receita para a Maria Souza": {
        "intent": "preparar_receita",
        "argumentos": {"busca": "Maria Souza"},
    },
}


def interpretar_mensagem(mensagem: str) -> dict | None:
    """Retorna ``{"intent": ..., "argumentos": {...}}`` para uma mensagem
    conhecida do catálogo fixo, ou ``None`` se a mensagem não bater com
    nenhum cenário mockado (ver `CENARIOS_MOCK` acima)."""
    return CENARIOS_MOCK.get(mensagem.strip())


class AgenteRequest(BaseModel):
    mensagem: str = Field(..., min_length=1, max_length=1000)


class AgenteAcao(BaseModel):
    """Uma tool executada em resposta à mensagem — trilha de transparência do
    agente (o que foi chamado, com quais argumentos, e o que retornou)."""

    tool: str
    argumentos: dict = Field(default_factory=dict)
    resultado: dict = Field(default_factory=dict)


class AgenteLink(BaseModel):
    label: str
    href: str


class AgenteResponse(BaseModel):
    resposta: str
    acoes: list[AgenteAcao] = Field(default_factory=list)
    links: list[AgenteLink] = Field(default_factory=list)
    mock: bool = Field(
        default=True,
        description="true enquanto a interpretação for simulada (exact match); passa a false quando plugada a um LLM real (contrato não muda)",
    )
    aviso: str | None = Field(
        default=None,
        description="Mensagem a exibir no frontend quando mock=true; null/ausente quando a interpretação for real",
    )
