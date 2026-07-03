"""Configuração central da aplicação.

Todas as configurações são carregadas de variáveis de ambiente (com defaults
seguros para desenvolvimento local via Docker Compose). Em produção, injete os
valores reais — em especial ``JWT_SECRET`` e as credenciais de storage.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Aplicação -------------------------------------------------------
    app_name: str = "Aureye API"
    environment: str = "development"  # development | production
    api_prefix: str = "/api"

    # Origens permitidas para CORS (frontend). Aceita lista separada por
    # vírgula na variável de ambiente CORS_ORIGINS.
    cors_origins: str = "http://localhost:5173,http://localhost:4173,http://localhost"

    # --- MongoDB ---------------------------------------------------------
    mongo_uri: str = "mongodb://mongodb:27017"
    mongo_db_name: str = "aureye"

    # --- Sessão / JWT ----------------------------------------------------
    # ATENÇÃO: troque JWT_SECRET em produção por um valor forte e secreto.
    jwt_secret: str = "dev-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60 * 24 * 7  # 7 dias

    cookie_name: str = "aureye_session"
    # Em produção (HTTPS) mantenha secure=true. Em dev local via http o
    # cookie ainda funciona em localhost mesmo com secure=false.
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    cookie_domain: str | None = None

    # --- Autenticação Google --------------------------------------------
    # Client ID do Google Identity Services. Necessário para validar o
    # id_token recebido do frontend em produção.
    google_client_id: str | None = None

    # Login de desenvolvimento: quando habilitado, expõe POST /auth/dev-login
    # que emite sessão para qualquer e-mail que já esteja na allowlist,
    # SEM precisar configurar OAuth do Google. NUNCA habilite em produção.
    dev_auth_enabled: bool = True

    # E-mail semeado como admin na primeira subida (allowlist inicial).
    # O cadastro de usuários é manual (ver SPEC), então precisamos de ao
    # menos um usuário para conseguir logar na primeira vez.
    seed_admin_email: str | None = None

    # --- Storage (MinIO / S3) -------------------------------------------
    # endpoint interno: usado pelo backend para operações de bucket
    # (dentro da rede do Docker Compose, host = "minio").
    s3_endpoint_internal: str = "http://minio:9000"
    # endpoint público: usado para ASSINAR as presigned URLs que o browser
    # vai acessar diretamente (host acessível pelo navegador, ex localhost).
    # Trocar por S3 real no futuro é só mudar estas variáveis + credenciais.
    s3_endpoint_public: str = "http://localhost:9000"
    # Endpoint usado para ASSINAR (SigV4 assina o header Host). Normalmente
    # igual a s3_endpoint_public. Só difira quando um proxy entre o browser e
    # o MinIO reescreve o header Host antes de repassar a requisição (ex:
    # port-forwarding do GitHub Codespaces, que sempre entrega Host:
    # localhost:<porta> pro container, mesmo quando acessado por um domínio
    # público) — nesse caso a URL final ainda usa s3_endpoint_public (é o
    # host que o navegador precisa alcançar), mas a assinatura é calculada
    # com este host, que é o que o MinIO efetivamente vai enxergar.
    s3_sign_endpoint: str | None = None
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "receitas"
    s3_region: str = "us-east-1"
    s3_presign_expires: int = 60 * 15  # 15 min

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
