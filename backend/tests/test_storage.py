"""Testes de geração de presigned URL (offline — boto3 não faz rede aqui)."""
from urllib.parse import urlparse

import pytest

from app import storage
from app.config import settings


def test_allowed_content_types():
    assert storage.allowed_content_type("image/jpeg")
    assert storage.allowed_content_type("application/pdf")
    assert not storage.allowed_content_type("text/html")


def test_upload_url_usa_endpoint_publico_e_key_correta():
    url, key = storage.generate_upload_url("image/png")
    # a URL assinada precisa apontar pro host que o navegador acessa
    assert urlparse(url).netloc == urlparse(settings.s3_endpoint_public).netloc
    assert key.startswith("receitas/")
    assert key.endswith(".png")
    assert settings.s3_bucket in url


def test_view_url_gera_get_assinado():
    url = storage.generate_view_url("receitas/abc.jpg")
    assert "X-Amz-Signature" in url or "AWSAccessKeyId" in url
    assert "receitas/abc.jpg" in url
