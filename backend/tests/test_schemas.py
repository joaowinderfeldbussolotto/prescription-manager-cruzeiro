"""Testes de validação de schema e regras de negócio (sem dependência de DB)."""
from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.cliente import ClienteCreate
from app.schemas.receita import ReceitaCreate, ReceitaPublic, add_12_months


# --- Cliente -------------------------------------------------------------

def test_cliente_minimo_valido():
    c = ClienteCreate(nome="Maria Silva", telefone="(11) 99999-0000")
    assert c.nome == "Maria Silva"
    assert c.cpf is None


def test_cliente_nome_obrigatorio():
    with pytest.raises(ValidationError):
        ClienteCreate(telefone="123")


@pytest.mark.parametrize("cpf", ["123.456.789-00", "12345678900"])
def test_cpf_formato_valido(cpf):
    c = ClienteCreate(nome="X", telefone="1", cpf=cpf)
    assert c.cpf == cpf


@pytest.mark.parametrize("cpf", ["123", "abc.def.ghi-jk", "123.456.789"])
def test_cpf_formato_invalido(cpf):
    with pytest.raises(ValidationError):
        ClienteCreate(nome="X", telefone="1", cpf=cpf)


def test_cpf_vazio_vira_none():
    c = ClienteCreate(nome="X", telefone="1", cpf="   ")
    assert c.cpf is None


# --- Receita -------------------------------------------------------------

# A imagem é o ÚNICO campo obrigatório para cadastrar uma receita.
IMG = "receitas/abc123.jpg"


def test_imagem_obrigatoria():
    with pytest.raises(ValidationError):
        ReceitaCreate(data_emissao=date(2025, 3, 1))


def test_so_a_imagem_basta():
    # sem datas, sem grau, sem médico — apenas a imagem
    r = ReceitaCreate(imagem_key=IMG)
    assert r.imagem_key == IMG


def test_data_emissao_default_hoje():
    r = ReceitaCreate(imagem_key=IMG)
    assert r.data_emissao == date.today()
    assert r.validade == add_12_months(date.today())


def test_validade_default_mais_12_meses():
    r = ReceitaCreate(imagem_key=IMG, data_emissao=date(2025, 3, 1), od_esferico=-2.5)
    assert r.validade == date(2026, 3, 1)


def test_validade_editavel():
    r = ReceitaCreate(
        imagem_key=IMG, data_emissao=date(2025, 3, 1), validade=date(2025, 9, 1), oe_esferico=1.0
    )
    assert r.validade == date(2025, 9, 1)


def test_validade_anterior_a_emissao_rejeitada():
    with pytest.raises(ValidationError):
        ReceitaCreate(
            imagem_key=IMG, data_emissao=date(2025, 3, 1), validade=date(2025, 1, 1)
        )


def test_grau_opcional_um_olho_so():
    r = ReceitaCreate(imagem_key=IMG, data_emissao=date(2025, 3, 1), oe_esferico=-1.25)
    assert r.od_esferico is None and r.oe_esferico == -1.25


def test_eixo_fora_de_faixa():
    with pytest.raises(ValidationError):
        ReceitaCreate(imagem_key=IMG, data_emissao=date(2025, 3, 1), od_eixo=200)


def test_add_12_months_ano_bissexto():
    assert add_12_months(date(2024, 2, 29)) == date(2025, 2, 28)


def test_receita_public_coage_datetime_para_date():
    doc = dict(
        id="a",
        cliente_id="b",
        data_emissao=datetime(2025, 1, 10, tzinfo=timezone.utc),
        validade=datetime(2026, 1, 10, tzinfo=timezone.utc),
        data_cadastro=datetime(2025, 1, 10, 12, 0, tzinfo=timezone.utc),
        imagem_key=IMG,
    )
    rp = ReceitaPublic(**doc)
    assert rp.data_emissao == date(2025, 1, 10)
    assert rp.validade == date(2026, 1, 10)
