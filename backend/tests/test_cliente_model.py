"""Testes de `app.models.cliente` — checagem de telefone duplicado e
persistência de acompanhamentos.

Sem MongoDB real (integração roda via Docker Compose): usamos um fake
mínimo da collection, só com o que `cliente_repo` chama (`find_one`,
`insert_one`, `find_one_and_update`, `update_one`), guardando os documentos
numa lista em memória. Suficiente pra exercitar a regra de negócio sem
precisar de infraestrutura externa.
"""
from __future__ import annotations

from datetime import date, datetime

import bson
import pytest
from bson import ObjectId

from app.models import cliente as cliente_repo


class _FakeInsertResult:
    def __init__(self, inserted_id: ObjectId):
        self.inserted_id = inserted_id


class _FakeUpdateResult:
    def __init__(self, modified_count: int):
        self.modified_count = modified_count


class _FakeClientesCollection:
    def __init__(self, docs: list[dict]):
        self._docs = docs

    @staticmethod
    def _matches(doc: dict, query: dict) -> bool:
        for key, value in query.items():
            if key == "acompanhamentos.id":
                if not any(a.get("id") == value for a in doc.get("acompanhamentos", [])):
                    return False
            elif isinstance(value, dict) and "$ne" in value:
                if doc.get(key) == value["$ne"]:
                    return False
            elif doc.get(key) != value:
                return False
        return True

    async def find_one(self, query: dict) -> dict | None:
        for doc in self._docs:
            if self._matches(doc, query):
                return dict(doc)
        return None

    async def insert_one(self, doc: dict) -> _FakeInsertResult:
        doc = dict(doc)
        doc["_id"] = ObjectId()
        self._docs.append(doc)
        return _FakeInsertResult(doc["_id"])

    async def find_one_and_update(self, query: dict, update: dict, return_document=None) -> dict | None:
        for doc in self._docs:
            if self._matches(doc, query):
                doc.update(update.get("$set", {}))
                return dict(doc)
        return None

    async def update_one(self, query: dict, update: dict) -> _FakeUpdateResult:
        for doc in self._docs:
            if self._matches(doc, query):
                if "$push" in update:
                    for field, value in update["$push"].items():
                        doc.setdefault(field, []).append(value)
                if "$set" in update:
                    for field, value in update["$set"].items():
                        if "." in field:
                            # suporta o `$` posicional simplificado usado em
                            # mark_acompanhamento_done ("acompanhamentos.$.concluido")
                            lista_campo, _, resto = field.partition(".$.")
                            alvo_id = query.get(f"{lista_campo}.id")
                            for item in doc.get(lista_campo, []):
                                if item.get("id") == alvo_id:
                                    item[resto] = value
                        else:
                            doc[field] = value
                return _FakeUpdateResult(modified_count=1)
        return _FakeUpdateResult(modified_count=0)


class _FakeDB:
    def __init__(self, docs: list[dict]):
        self.clientes = _FakeClientesCollection(docs)


def _doc(nome: str, telefone: str, *, deletado: bool = False, **extra) -> dict:
    return {"_id": ObjectId(), "nome": nome, "telefone": telefone, "deletado": deletado, **extra}


async def test_create_recusa_telefone_duplicado():
    db = _FakeDB([_doc("Maria Souza", "11999999999")])

    with pytest.raises(cliente_repo.ClienteDuplicadoError, match="Maria Souza"):
        await cliente_repo.create(db, {"nome": "Maria Outra", "telefone": "11999999999"})


async def test_create_permite_telefone_novo():
    db = _FakeDB([_doc("Maria Souza", "11999999999")])

    criado = await cliente_repo.create(db, {"nome": "João Silva", "telefone": "11888888888"})

    assert criado["nome"] == "João Silva"


async def test_create_permite_telefone_de_cliente_soft_deletado():
    """Telefone de um cliente soft-deletado (`deletado=True`) pode ser
    reaproveitado por um cadastro novo — a checagem só olha clientes ativos."""
    db = _FakeDB([_doc("Maria Antiga", "11999999999", deletado=True)])

    criado = await cliente_repo.create(db, {"nome": "Maria Nova", "telefone": "11999999999"})

    assert criado["nome"] == "Maria Nova"


async def test_update_recusa_telefone_duplicado_de_outro_cliente():
    a = _doc("Cliente A", "11111111111")
    b = _doc("Cliente B", "22222222222")
    db = _FakeDB([a, b])

    with pytest.raises(cliente_repo.ClienteDuplicadoError, match="Cliente A"):
        await cliente_repo.update(db, str(b["_id"]), {"telefone": "11111111111"})


async def test_update_permite_manter_proprio_telefone():
    """Editar outros campos sem mudar o telefone (ou mantendo o mesmo valor)
    não deve disparar falso positivo de duplicidade contra si mesmo."""
    a = _doc("Cliente A", "11111111111")
    db = _FakeDB([a])

    atualizado = await cliente_repo.update(
        db, str(a["_id"]), {"telefone": "11111111111", "email": "a@teste.com"}
    )

    assert atualizado["email"] == "a@teste.com"


async def test_add_acompanhamento_converte_date_para_datetime():
    """Regressão: `data_agendada` chega como `date` puro (vindo da tool do
    agente) — BSON não tem tipo `date` (só `datetime`), então gravar sem
    converter levanta `InvalidDocument` assim que toca um Mongo de verdade.
    `add_acompanhamento` precisa normalizar antes do `$push`."""
    a = _doc("Cliente A", "11111111111")
    db = _FakeDB([a])

    ok = await cliente_repo.add_acompanhamento(
        db,
        str(a["_id"]),
        {
            "id": "ac1",
            "data_agendada": date(2026, 1, 20),
            "tipo": "ligar",
            "descricao": "oferecer desconto",
            "concluido": False,
        },
    )

    assert ok is True
    salvo = a["acompanhamentos"][0]
    assert isinstance(salvo["data_agendada"], datetime)
    # a prova real: o doc resultante precisa ser codificável em BSON
    bson.encode({"data_agendada": salvo["data_agendada"]})


async def test_mark_acompanhamento_done():
    a = _doc(
        "Cliente A",
        "11111111111",
        acompanhamentos=[
            {
                "id": "ac1",
                "data_agendada": datetime(2026, 1, 20),
                "tipo": "ligar",
                "descricao": "x",
                "concluido": False,
            }
        ],
    )
    db = _FakeDB([a])

    ok = await cliente_repo.mark_acompanhamento_done(db, str(a["_id"]), "ac1")

    assert ok is True
    assert a["acompanhamentos"][0]["concluido"] is True
