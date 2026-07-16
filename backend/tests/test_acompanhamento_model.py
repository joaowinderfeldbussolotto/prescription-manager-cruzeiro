"""Testes de `app.models.acompanhamento` — collection própria, listagem
SEMPRE por responsável (usuario_id), nunca por cliente (ver docstring de
`app.schemas.acompanhamento` pro motivo).

Sem MongoDB real: fake mínimo da collection cobrindo só o que o repo usa
(`insert_one`, `count_documents`, `find().sort().skip().limit().to_list()`,
`find_one_and_update`).
"""
from __future__ import annotations

from datetime import date, datetime

import bson
from bson import ObjectId

from app.models import acompanhamento as acompanhamento_repo


class _FakeInsertResult:
    def __init__(self, inserted_id: ObjectId):
        self.inserted_id = inserted_id


class _FakeCursor:
    def __init__(self, docs: list[dict]):
        self._docs = list(docs)

    def sort(self, field: str, direction: int) -> "_FakeCursor":
        self._docs.sort(key=lambda d: d.get(field), reverse=(direction < 0))
        return self

    def skip(self, n: int) -> "_FakeCursor":
        self._docs = self._docs[n:]
        return self

    def limit(self, n: int) -> "_FakeCursor":
        self._docs = self._docs[:n]
        return self

    async def to_list(self, length: int | None = None) -> list[dict]:
        return list(self._docs)


class _FakeAcompanhamentosCollection:
    def __init__(self, docs: list[dict]):
        self._docs = docs

    @staticmethod
    def _matches(doc: dict, query: dict) -> bool:
        return all(doc.get(k) == v for k, v in query.items())

    async def insert_one(self, doc: dict) -> _FakeInsertResult:
        doc = dict(doc)
        doc["_id"] = ObjectId()
        self._docs.append(doc)
        return _FakeInsertResult(doc["_id"])

    async def count_documents(self, query: dict) -> int:
        return sum(1 for d in self._docs if self._matches(d, query))

    def find(self, query: dict) -> _FakeCursor:
        return _FakeCursor([d for d in self._docs if self._matches(d, query)])

    async def find_one_and_update(self, query: dict, update: dict, return_document=None) -> dict | None:
        for doc in self._docs:
            if self._matches(doc, query):
                doc.update(update.get("$set", {}))
                return dict(doc)
        return None


class _FakeDB:
    def __init__(self, docs: list[dict]):
        self.acompanhamentos = _FakeAcompanhamentosCollection(docs)


def _doc(cliente_nome: str, usuario_id: str, *, concluido: bool = False, **extra) -> dict:
    return {
        "_id": ObjectId(),
        "cliente_id": "cliente-1",
        "cliente_nome": cliente_nome,
        "usuario_id": usuario_id,
        "usuario_nome": "Atendente",
        "data_agendada": datetime(2026, 3, 1),
        "tipo": "ligar",
        "descricao": "x",
        "concluido": concluido,
        **extra,
    }


async def test_create_converte_date_para_datetime():
    """Mesma causa raiz do bug visto em `verificar_validade_receita`: BSON
    não serializa `date` puro (só `datetime`) — sem converter, o insert
    levantaria `InvalidDocument` assim que tocasse um Mongo de verdade."""
    db = _FakeDB([])

    criado = await acompanhamento_repo.create(
        db,
        {
            "cliente_id": "c1",
            "cliente_nome": "Maria",
            "usuario_id": "u1",
            "usuario_nome": "Atendente",
            "data_agendada": date(2026, 1, 20),
            "tipo": "ligar",
            "descricao": "oferecer desconto",
        },
    )

    salvo = db.acompanhamentos._docs[0]
    assert isinstance(salvo["data_agendada"], datetime)
    bson.encode({"data_agendada": salvo["data_agendada"]})  # prova real: é codificável
    assert criado["concluido"] is False


async def test_list_by_responsavel_filtra_por_usuario_nao_por_cliente():
    """Dois clientes diferentes, mesmo usuario_id, aparecem juntos; um
    acompanhamento de OUTRO usuario_id não aparece — a listagem é por
    responsável, nunca por cliente."""
    meu1 = _doc("Cliente A", "u1")
    meu2 = _doc("Cliente B", "u1")
    de_outro = _doc("Cliente C", "u2")
    db = _FakeDB([meu1, meu2, de_outro])

    itens, total = await acompanhamento_repo.list_by_responsavel(db, "u1")

    assert total == 2
    assert {i["cliente_nome"] for i in itens} == {"Cliente A", "Cliente B"}


async def test_list_by_responsavel_filtro_pendentes_default():
    pendente = _doc("Cliente A", "u1", concluido=False)
    feito = _doc("Cliente B", "u1", concluido=True)
    db = _FakeDB([pendente, feito])

    itens, total = await acompanhamento_repo.list_by_responsavel(db, "u1")

    assert total == 1
    assert itens[0]["cliente_nome"] == "Cliente A"


async def test_list_by_responsavel_filtro_concluido():
    pendente = _doc("Cliente A", "u1", concluido=False)
    feito = _doc("Cliente B", "u1", concluido=True)
    db = _FakeDB([pendente, feito])

    itens, total = await acompanhamento_repo.list_by_responsavel(db, "u1", filtro="concluido")

    assert total == 1
    assert itens[0]["cliente_nome"] == "Cliente B"


async def test_list_by_responsavel_filtro_todos():
    pendente = _doc("Cliente A", "u1", concluido=False)
    feito = _doc("Cliente B", "u1", concluido=True)
    db = _FakeDB([pendente, feito])

    itens, total = await acompanhamento_repo.list_by_responsavel(db, "u1", filtro="todos")

    assert total == 2


async def test_mark_done_escopado_ao_usuario():
    """Um atendente não consegue concluir o acompanhamento de outro, mesmo
    sabendo o id (mark_done escopa a query por usuario_id)."""
    de_outro = _doc("Cliente A", "u2")
    db = _FakeDB([de_outro])

    resultado = await acompanhamento_repo.mark_done(db, str(de_outro["_id"]), "u1")

    assert resultado is None


async def test_mark_done_sucesso():
    meu = _doc("Cliente A", "u1")
    db = _FakeDB([meu])

    resultado = await acompanhamento_repo.mark_done(db, str(meu["_id"]), "u1")

    assert resultado is not None
    assert resultado["concluido"] is True
