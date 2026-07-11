#!/bin/bash
# User-data da instância EC2 — roda uma única vez, no primeiro boot.
#
# Instala Docker + Docker Compose, clona o repositório (público, sem auth),
# gera um .env de produção (nunca usa os defaults de dev) e sobe o
# docker-compose.yml existente sem modificar nada nele — mongodb e minio
# continuam containerizados, exatamente como em dev local.
set -euxo pipefail

REPO_URL="https://github.com/joaowinderfeldbussolotto/prescription-manager-cruzeiro.git"
# A PR ainda não foi mergeada na main — todo o código (docker-compose.yml
# incluso) vive nesta branch. Clonar a default (main) traz um repo vazio.
REPO_BRANCH="claude/agente-chat-mock"
APP_DIR="/opt/app"

# --- Docker + Compose + Buildx plugins --------------------------------------
dnf update -y
dnf install -y docker git jq
systemctl enable --now docker
usermod -aG docker ec2-user

mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# `docker compose build`/`up --build` exige o plugin buildx (não vem
# junto com o pacote `docker` do AL2023) — mesmo padrão de instalação do
# docker-compose acima, baixando o binário da release mais recente.
BUILDX_VERSION=$(curl -fsSL https://api.github.com/repos/docker/buildx/releases/latest | jq -r .tag_name)
curl -fSL "https://github.com/docker/buildx/releases/download/${BUILDX_VERSION}/buildx-${BUILDX_VERSION}.linux-amd64" \
  -o /usr/local/lib/docker/cli-plugins/docker-buildx
chmod +x /usr/local/lib/docker/cli-plugins/docker-buildx

# --- Swap ---------------------------------------------------------------
# t2.micro tem só 1GiB de RAM — mongodb+minio+backend+frontend juntos é
# apertado. Um swap de 2GB (grátis, só usa espaço do EBS que já existe)
# reduz bastante o risco de OOM kill quando a memória aperta.
if [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

# --- Código (repo público, sem autenticação) --------------------------------
mkdir -p "$APP_DIR"
cd "$APP_DIR"
git clone --depth 1 --branch "$REPO_BRANCH" "$REPO_URL" .
ls -la "$APP_DIR"  # log de diagnóstico: confirma o que o clone trouxe
if [ ! -f "$APP_DIR/docker-compose.yml" ]; then
  echo "ERRO: docker-compose.yml não encontrado em $APP_DIR após o clone." >&2
  exit 1
fi

# --- IP público via IMDSv2 ---------------------------------------------
# Funciona corretamente mesmo com Elastic IP: o deploy.sh associa o EIP
# logo após lançar a instância, bem antes do boot chegar até aqui (os
# passos de dnf/install acima levam alguns minutos).
TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" \
  -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
PUBLIC_IP=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" \
  http://169.254.169.254/latest/meta-data/public-ipv4)

# --- .env de produção ----------------------------------------------------
# Nunca usa os defaults de dev (JWT_SECRET/credenciais do MinIO). A porta
# 9000 (MinIO) fica pública nesta configuração — ver deploy.sh — por isso
# as credenciais do MinIO aqui são aleatórias, não "minioadmin".
cat > "$APP_DIR/.env" <<EOF
JWT_SECRET=$(openssl rand -hex 32)
COOKIE_SECURE=false
CORS_ORIGINS=http://${PUBLIC_IP}:8080
DEV_AUTH_ENABLED=true
SEED_ADMIN_EMAIL=admin@example.com
S3_ACCESS_KEY=$(openssl rand -hex 12)
S3_SECRET_KEY=$(openssl rand -hex 24)
S3_ENDPOINT_PUBLIC=http://${PUBLIC_IP}:9000
EOF
chmod 600 "$APP_DIR/.env"

# --- Sobe tudo -----------------------------------------------------------
# Builda as imagens na própria instância (sem ECR/registry — mais simples,
# mas o primeiro boot demora alguns minutos, principalmente o build do
# frontend/Vite). `-f`/`--project-directory` explícitos: não depende do
# diretório de trabalho corrente estar certo neste ponto do script.
cd "$APP_DIR"
docker compose --project-directory "$APP_DIR" -f "$APP_DIR/docker-compose.yml" up -d --build

echo "=== deploy concluído. Backend/frontend em http://${PUBLIC_IP}:8080 ===" \
  >> /var/log/user-data-status.log
