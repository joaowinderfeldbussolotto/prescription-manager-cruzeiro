"""Testes de `app.models.cliente` — checagem de telefone/CPF duplicado.

Sem MongoDB real (integração roda via Docker Compose): usamos um fake
mínimo da collection, só com o que `cliente_repo.create`/`update` chamam
(`find_one`, `insert_one`, `find_one_and_update`), guardando os documentos
numa lista em memória. Suficiente pra exercitar a regra de negócio sem
precisar de infraestrutura externa.
"""
from __future__ import annotations

import pytest
from bson import ObjectId

from app.models import cliente as cliente_repo


class _FakeInsertResult:
    def __init__(self, inserted_id: ObjectId):
        self.inserted_id = inserted_id


class _FakeClientesCollection:
    def __init__(self, docs: list[dict]):
        self._docs = docs

    @staticmethod
    def _matches(doc: dict, query: dict) -> bool:
        for key, value in query.items():
            if isinstance(value, dict) and "$ne" in value:
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


async def test_create_recusa_cpf_duplicado():
    db = _FakeDB([_doc("Maria Souza", "11999999999", cpf="123.456.789-00")])

    with pytest.raises(cliente_repo.ClienteDuplicadoError, match="Maria Souza"):
        await cliente_repo.create(
            db, {"nome": "Maria Outra", "telefone": "11888888888", "cpf": "123.456.789-00"}
        )


async def test_create_permite_sem_cpf_informado():
    """Cliente sem CPF (campo opcional) não deve disparar checagem nenhuma."""
    db = _FakeDB([_doc("Maria Souza", "11999999999", cpf="123.456.789-00")])

    criado = await cliente_repo.create(db, {"nome": "João Silva", "telefone": "11888888888"})

    assert criado["nome"] == "João Silva"


async def test_update_recusa_cpf_duplicado_de_outro_cliente():
    a = _doc("Cliente A", "11111111111", cpf="123.456.789-00")
    b = _doc("Cliente B", "22222222222", cpf="999.999.999-99")
    db = _FakeDB([a, b])

    with pytest.raises(cliente_repo.ClienteDuplicadoError, match="Cliente A"):
        await cliente_repo.update(db, str(b["_id"]), {"cpf": "123.456.789-00"})


async def test_update_apenas_cpf_sem_telefone_no_payload():
    """Editar só o CPF (sem telefone no payload) ainda deve checar duplicidade
    de CPF normalmente — os dois campos são checados independentemente."""
    a = _doc("Cliente A", "11111111111", cpf="111.111.111-11")
    b = _doc("Cliente B", "22222222222", cpf="222.222.222-22")
    db = _FakeDB([a, b])

    with pytest.raises(cliente_repo.ClienteDuplicadoError, match="Cliente A"):
        await cliente_repo.update(db, str(b["_id"]), {"cpf": "111.111.111-11"})


async def test_create_trim_pega_duplicata_mesmo_com_espacos_no_input():
    """Espaço em branco (acidental, ex.: colado de outro sistema) no valor
    recebido não pode driblar a checagem de duplicidade."""
    db = _FakeDB([_doc("Maria Souza", "11999999999")])

    with pytest.raises(cliente_repo.ClienteDuplicadoError, match="Maria Souza"):
        await cliente_repo.create(db, {"nome": "Maria Outra", "telefone": "  11999999999  "})


async def test_create_persiste_telefone_e_cpf_sem_espacos():
    """O valor persistido também é normalizado (trim) — não só o valor usado
    na comparação — pra uma checagem futura por exact-match continuar
    funcionando de forma consistente."""
    db = _FakeDB([])

    criado = await cliente_repo.create(
        db,
        {
            "nome": "João Silva",
            "telefone": "  11888888888  ",
            "cpf": " 123.456.789-00 ",
        },
    )

    assert criado["telefone"] == "11888888888"
    assert criado["cpf"] == "123.456.789-00"
