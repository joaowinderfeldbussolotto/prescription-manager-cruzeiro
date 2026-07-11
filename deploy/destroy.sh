#!/bin/bash
# Desfaz tudo que o deploy.sh criou (lê os IDs de ./.deploy-state).
# Útil pra não continuar pagando se decidir parar de usar o deploy.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if [ ! -f .deploy-state ]; then
  echo "Não achei .deploy-state — nada pra destruir (ou já foi destruído)."
  exit 1
fi
# shellcheck source=/dev/null
source .deploy-state

read -r -p "Isso vai terminar a instância $INSTANCE_ID e liberar o Elastic IP. Confirma? (digite 'sim'): " CONFIRM
if [ "$CONFIRM" != "sim" ]; then
  echo "Cancelado."
  exit 0
fi

echo "Terminando instância $INSTANCE_ID..."
aws ec2 terminate-instances --region "$REGION" --instance-ids "$INSTANCE_ID" >/dev/null
aws ec2 wait instance-terminated --region "$REGION" --instance-ids "$INSTANCE_ID"

echo "Liberando Elastic IP $ALLOC_ID..."
aws ec2 release-address --region "$REGION" --allocation-id "$ALLOC_ID" >/dev/null

echo "Removendo security group $SG_ID..."
aws ec2 delete-security-group --region "$REGION" --group-id "$SG_ID" >/dev/null

echo "Key pair '$KEY_NAME' NÃO foi removido (a chave .pem local ainda é sua)."
echo "Pra apagar também: aws ec2 delete-key-pair --region $REGION --key-name $KEY_NAME"

rm -f .deploy-state
echo "Pronto — recursos destruídos."
