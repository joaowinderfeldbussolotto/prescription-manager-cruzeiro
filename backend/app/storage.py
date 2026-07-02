"""Storage de imagens via MinIO (API compatível com S3).

> Nota de migração (SPEC): MinIO → S3 é quase transparente. O mesmo client
> ``boto3`` funciona nos dois; muda só ``endpoint_url`` e credenciais via
> variável de ambiente. O código de presigned URL abaixo não muda.

Detalhe importante do Docker Compose: o backend fala com o MinIO pelo host
interno da rede (``minio:9000``), mas as presigned URLs precisam ser assinadas
com o host que o NAVEGADOR consegue acessar (``localhost:9000``). Por isso
mantemos dois clients:

- ``_client_internal``  -> operações servidor-a-servidor (criar bucket)
- ``_client_public``    -> gerar as presigned URLs (PUT/GET) usadas no browser
"""
from __future__ import annotations

import logging
import time
import uuid
from functools import lru_cache

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.config import settings

logger = logging.getLogger(__name__)

# content-type -> extensão de arquivo aceita para upload de imagem de receita
_ALLOWED_CONTENT_TYPES: dict[str, str] = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "application/pdf": "pdf",
}


def allowed_content_type(content_type: str) -> bool:
    return content_type in _ALLOWED_CONTENT_TYPES


def _build_client(endpoint_url: str):
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        # SigV4 + path-style: necessário pro MinIO (e compatível com S3).
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


@lru_cache
def _client_internal():
    return _build_client(settings.s3_endpoint_internal)


@lru_cache
def _client_public():
    return _build_client(settings.s3_endpoint_public)


def ensure_bucket(retries: int = 10, delay: float = 1.5) -> None:
    """Garante que o bucket existe. MinIO não cria bucket automaticamente.

    Tenta algumas vezes porque, no Docker Compose, o MinIO pode subir alguns
    segundos depois do backend. (O serviço ``minio-init`` do compose também
    cria o bucket de forma independente — aqui é defesa em profundidade.)
    """
    client = _client_internal()
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            try:
                client.head_bucket(Bucket=settings.s3_bucket)
                logger.info("Bucket '%s' já existe", settings.s3_bucket)
            except ClientError:
                client.create_bucket(Bucket=settings.s3_bucket)
                logger.info("Bucket '%s' criado", settings.s3_bucket)
            return
        except (BotoCoreError, ClientError) as exc:  # MinIO ainda não respondeu
            last_err = exc
            if attempt < retries:
                time.sleep(delay)
    logger.warning("Não foi possível garantir o bucket após %d tentativas: %s", retries, last_err)


def generate_upload_url(content_type: str) -> tuple[str, str]:
    """Gera uma presigned URL de PUT + a chave do objeto.

    Retorna ``(upload_url, key)``. O frontend faz PUT direto no ``upload_url``
    (com o header Content-Type correspondente) e depois envia ``key`` no
    create/update da receita.
    """
    ext = _ALLOWED_CONTENT_TYPES[content_type]
    key = f"receitas/{uuid.uuid4().hex}.{ext}"
    url = _client_public().generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.s3_bucket,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=settings.s3_presign_expires,
    )
    return url, key


def generate_view_url(key: str) -> str:
    """Gera uma presigned URL de GET pra visualizar a imagem no browser."""
    return _client_public().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=settings.s3_presign_expires,
    )


def delete_object(key: str) -> None:
    try:
        _client_internal().delete_object(Bucket=settings.s3_bucket, Key=key)
    except ClientError:  # pragma: no cover - best effort
        logger.warning("Falha ao remover objeto '%s' do storage", key)
