#!/bin/bash
# Provisiona a infraestrutura AWS pro deploy simples (EC2 t2.micro rodando
# o docker-compose.yml existente via user-data.sh).
#
# Uso: configure as variáveis abaixo, rode `./deploy.sh` a partir desta
# pasta (precisa do AWS CLI configurado com credenciais válidas).
#
# Roda uma vez só. Rodar de novo cria recursos duplicados (nomes fixos) —
# pra recriar do zero, rode ./destroy.sh primeiro.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

# --- Configuração (ajuste se quiser) ----------------------------------------
REGION="us-east-1"
KEY_NAME="cruzeiro-app-key"
SG_NAME="cruzeiro-app-sg"
INSTANCE_NAME="cruzeiro-app"
INSTANCE_TYPE="t2.micro"
ROOT_VOLUME_SIZE_GB=20

echo "== 0/6: checando AWS CLI e credenciais =="
if ! command -v aws >/dev/null 2>&1; then
  echo "AWS CLI não encontrado. Instale: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html" >&2
  exit 1
fi
if ! aws sts get-caller-identity --region "$REGION" >/dev/null 2>&1; then
  echo "AWS CLI instalado, mas sem credenciais válidas. Rode 'aws configure' primeiro." >&2
  exit 1
fi

echo "== 1/6: par de chaves SSH =="
if aws ec2 describe-key-pairs --region "$REGION" --key-names "$KEY_NAME" >/dev/null 2>&1; then
  echo "Key pair '$KEY_NAME' já existe, pulando (a chave .pem precisa já estar salva localmente)."
else
  aws ec2 create-key-pair --region "$REGION" --key-name "$KEY_NAME" \
    --query 'KeyMaterial' --output text > "${KEY_NAME}.pem"
  chmod 400 "${KEY_NAME}.pem"
  echo "Chave salva em ./${KEY_NAME}.pem — guarde-a, não tem como baixar de novo."
fi

echo "== 2/6: VPC padrão da conta =="
VPC_ID=$(aws ec2 describe-vpcs --region "$REGION" \
  --filters Name=isDefault,Values=true \
  --query 'Vpcs[0].VpcId' --output text)
echo "VPC padrão: $VPC_ID"

echo "== 3/6: security group (22 SSH, 8080 app, 9000 MinIO S3 API) =="
# Porta 9000 precisa ficar pública: o upload/visualização de imagem de
# receita usa presigned URL acessada DIRETO pelo navegador no MinIO, sem
# passar pelo nginx/backend (ver storage.py). Só 8080 não seria suficiente.
SG_ID=$(aws ec2 describe-security-groups --region "$REGION" \
  --filters "Name=group-name,Values=$SG_NAME" "Name=vpc-id,Values=$VPC_ID" \
  --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || echo "None")

if [ "$SG_ID" = "None" ] || [ -z "$SG_ID" ]; then
  SG_ID=$(aws ec2 create-security-group --region "$REGION" \
    --group-name "$SG_NAME" \
    --description "Prescription Manager Cruzeiro - app (SSH/app/MinIO)" \
    --vpc-id "$VPC_ID" \
    --query 'GroupId' --output text)

  aws ec2 authorize-security-group-ingress --region "$REGION" --group-id "$SG_ID" \
    --ip-permissions \
      'IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{CidrIp=0.0.0.0/0,Description=SSH}]' \
      'IpProtocol=tcp,FromPort=8080,ToPort=8080,IpRanges=[{CidrIp=0.0.0.0/0,Description=App}]' \
      'IpProtocol=tcp,FromPort=9000,ToPort=9000,IpRanges=[{CidrIp=0.0.0.0/0,Description=MinIO S3 API}]' \
    >/dev/null
  echo "Security group criado: $SG_ID"
else
  echo "Security group '$SG_NAME' já existe: $SG_ID (pulando criação de regras)"
fi

echo "== 4/6: AMI mais recente do Amazon Linux 2023 (x86_64) =="
AMI_ID=$(aws ssm get-parameters --region "$REGION" \
  --names /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 \
  --query 'Parameters[0].Value' --output text)
echo "AMI: $AMI_ID"

echo "== 5/6: lançando a instância EC2 ($INSTANCE_TYPE) =="
INSTANCE_ID=$(aws ec2 run-instances --region "$REGION" \
  --image-id "$AMI_ID" \
  --instance-type "$INSTANCE_TYPE" \
  --key-name "$KEY_NAME" \
  --security-group-ids "$SG_ID" \
  --block-device-mappings "[{\"DeviceName\":\"/dev/xvda\",\"Ebs\":{\"VolumeSize\":$ROOT_VOLUME_SIZE_GB,\"VolumeType\":\"gp3\"}}]" \
  --user-data "file://user-data.sh" \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$INSTANCE_NAME}]" \
  --query 'Instances[0].InstanceId' --output text)
echo "Instância: $INSTANCE_ID (aguardando ficar 'running'...)"
aws ec2 wait instance-running --region "$REGION" --instance-ids "$INSTANCE_ID"

echo "== 6/6: Elastic IP (endereço estável) =="
ALLOC_ID=$(aws ec2 allocate-address --region "$REGION" --domain vpc \
  --query 'AllocationId' --output text)
aws ec2 associate-address --region "$REGION" \
  --instance-id "$INSTANCE_ID" --allocation-id "$ALLOC_ID" >/dev/null

PUBLIC_IP=$(aws ec2 describe-addresses --region "$REGION" \
  --allocation-ids "$ALLOC_ID" --query 'Addresses[0].PublicIp' --output text)

# Salva os IDs criados — usado pelo destroy.sh pra limpar tudo depois.
cat > .deploy-state <<EOF
REGION=$REGION
INSTANCE_ID=$INSTANCE_ID
SG_ID=$SG_ID
ALLOC_ID=$ALLOC_ID
KEY_NAME=$KEY_NAME
EOF

echo ""
echo "=== Instância no ar: http://${PUBLIC_IP}:8080 ==="
echo "O user-data ainda está rodando (instala docker, clona o repo, builda"
echo "as imagens) — leva alguns minutos. Acompanhe com:"
echo "  ssh -i ${KEY_NAME}.pem ec2-user@${PUBLIC_IP} 'tail -f /var/log/cloud-init-output.log'"
echo ""
echo "Quando terminar, teste:"
echo "  curl http://${PUBLIC_IP}:8080/api/health"
