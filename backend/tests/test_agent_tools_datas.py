"""Regressão: tools do agente que lidam com datas vindas do Mongo.

O Mongo sempre devolve `datetime` pra campos de data (BSON não tem `date`
puro — ver `app.db.serialization.date_to_datetime`/`as_date`). Comparar ou
subtrair um `datetime` com um `date` puro (ex.: `date.today()`) levanta
`TypeError: unsupported operand type(s) for -: 'datetime.datetime' and
'datetime.date'` — foi exatamente o erro relatado em produção na tool
`verificar_validade_receita`. Estes testes chamam as tools reais (via
`.ainvoke`), monkeypatchando só a busca de cliente/receitas, com os campos
de data no formato `datetime` que o Mongo de fato devolve — não o `date`
"ingênuo" que seria fácil de usar sem querer num teste e esconder o bug.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.agent import tools as agent_tools

CLIENTE = {"id": "507f1f77bcf86cd799439011", "nome": "Maria Souza", "telefone": "11999999999"}


@pytest.fixture(autouse=True)
def _fake_db(monkeypatch):
    """As tools chamam `get_db()` antes de repassar pro repo — nestes testes
    o repo em si é monkeypatchado e ignora o `db`, mas a chamada precisa não
    levantar `MongoDB não inicializado` primeiro."""
    monkeypatch.setattr(agent_tools, "get_db", lambda: object())


def _receita(validade: datetime, **extra) -> dict:
    return {
        "id": "665aaa",
        "data_emissao": validade - timedelta(days=365),
        "validade": validade,
        "medico_nome": "Dr. Silva",
        **extra,
    }


async def _fake_buscar_um_cliente(termo, limit=10):
    return [CLIENTE]


async def test_verificar_validade_receita_valida(monkeypatch):
    # validade como datetime tz-aware, exatamente como o Mongo devolve
    validade = datetime.now(timezone.utc) + timedelta(days=400)
    monkeypatch.setattr(agent_tools, "_buscar_clientes", _fake_buscar_um_cliente)

    async def fake_list_by_cliente(db, cliente_id):
        return [_receita(validade)]

    monkeypatch.setattr(agent_tools.receita_repo, "list_by_cliente", fake_list_by_cliente)

    resultado = await agent_tools.verificar_validade_receita.ainvoke({"cliente_nome": "Maria"})

    assert "✅" in resultado
    assert "válida" in resultado.lower()


async def test_verificar_validade_receita_vencendo(monkeypatch):
    validade = datetime.now(timezone.utc) + timedelta(days=10)
    monkeypatch.setattr(agent_tools, "_buscar_clientes", _fake_buscar_um_cliente)

    async def fake_list_by_cliente(db, cliente_id):
        return [_receita(validade)]

    monkeypatch.setattr(agent_tools.receita_repo, "list_by_cliente", fake_list_by_cliente)

    resultado = await agent_tools.verificar_validade_receita.ainvoke({"cliente_nome": "Maria"})

    assert "⚠️" in resultado
    assert "urgente" in resultado.lower()


async def test_verificar_validade_receita_expirada(monkeypatch):
    validade = datetime.now(timezone.utc) - timedelta(days=5)
    monkeypatch.setattr(agent_tools, "_buscar_clientes", _fake_buscar_um_cliente)

    async def fake_list_by_cliente(db, cliente_id):
        return [_receita(validade)]

    monkeypatch.setattr(agent_tools.receita_repo, "list_by_cliente", fake_list_by_cliente)

    resultado = await agent_tools.verificar_validade_receita.ainvoke({"cliente_nome": "Maria"})

    assert "❌" in resultado
    assert "expirou" in resultado.lower()


async def test_verificar_validade_receita_sem_receitas(monkeypatch):
    monkeypatch.setattr(agent_tools, "_buscar_clientes", _fake_buscar_um_cliente)

    async def fake_list_by_cliente(db, cliente_id):
        return []

    monkeypatch.setattr(agent_tools.receita_repo, "list_by_cliente", fake_list_by_cliente)

    resultado = await agent_tools.verificar_validade_receita.ainvoke({"cliente_nome": "Maria"})

    assert "não tem nenhuma receita" in resultado.lower()


async def test_listar_acompanhamentos_ordena_com_datetime_do_mongo(monkeypatch):
    """`data_agendada` volta do Mongo como `datetime` — a ordenação/formatação
    não pode quebrar nem misturar tipos."""
    cliente_com_acompanhamentos = {
        **CLIENTE,
        "acompanhamentos": [
            {
                "id": "ac2",
                "data_agendada": datetime(2026, 3, 1, tzinfo=timezone.utc),
                "tipo": "email",
                "descricao": "segunda",
                "concluido": False,
            },
            {
                "id": "ac1",
                "data_agendada": datetime(2026, 1, 1, tzinfo=timezone.utc),
                "tipo": "ligar",
                "descricao": "primeira",
                "concluido": False,
            },
        ],
    }

    async def fake_buscar(termo, limit=10):
        return [cliente_com_acompanhamentos]

    monkeypatch.setattr(agent_tools, "_buscar_clientes", fake_buscar)

    resultado = await agent_tools.listar_acompanhamentos.ainvoke({"cliente_nome": "Maria"})

    # "primeira" (01/01) deve aparecer antes de "segunda" (01/03)
    assert resultado.index("primeira") < resultado.index("segunda")
    assert "01/01/2026" in resultado
    assert "01/03/2026" in resultado
