"""Cobre a normalização date/datetime no update de receita (evita comparar
`date` do request com `datetime` do Mongo)."""
from datetime import date, datetime, timezone

from app.routers.receitas import _as_date
from app.schemas.receita import add_12_months


def test_as_date_from_datetime():
    assert _as_date(datetime(2025, 1, 10, 12, 0, tzinfo=timezone.utc)) == date(2025, 1, 10)


def test_as_date_from_date():
    assert _as_date(date(2025, 1, 10)) == date(2025, 1, 10)


def test_as_date_none():
    assert _as_date(None) is None


def test_comparacao_apos_normalizacao_nao_quebra():
    # cenário do bug: validade (date, do request) vs emissao (datetime, do Mongo)
    validade = _as_date(date(2026, 1, 10))
    emissao = _as_date(datetime(2025, 1, 10, tzinfo=timezone.utc))
    assert validade > emissao  # não levanta TypeError


def test_default_validade_quando_limpa():
    emissao = _as_date(datetime(2025, 3, 1, tzinfo=timezone.utc))
    assert add_12_months(emissao) == date(2026, 3, 1)
