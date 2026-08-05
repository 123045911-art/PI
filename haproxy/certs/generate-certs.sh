#!/usr/bin/env bash
# Genera (o regenera) el CA autofirmado y el certificado de servidor que usa
# HAProxy en compose.public.yaml.
#
# Uso local / de prueba (SAN = 127.0.0.1, ya en server.cnf): sin argumentos.
#
#   ./generate-certs.sh
#
# Para el despliegue real en AWS: edita server.cnf y cambia IP.1 por la IP
# publica real de la instancia (y/o agrega un DNS.1 si tienes dominio), luego
# vuelve a correr este script para regenerar el certificado con esa IP en el
# SAN antes de subirlo al servidor.
set -euo pipefail
cd "$(dirname "$0")"

DAYS_CA=3650
DAYS_SERVER=825

echo "==> Generando CA autofirmado..."
openssl genrsa -out CA.key 2048
openssl req -x509 -new -nodes -key CA.key -sha256 -days "$DAYS_CA" \
    -subj "/C=MX/ST=Queretaro/L=Queretaro/O=VisioFlow/OU=Seguridad/CN=VisioFlow Root CA" \
    -out CA.crt

echo "==> Generando llave y CSR del servidor (usando server.cnf)..."
openssl genrsa -out server.key 2048
openssl req -new -key server.key -out server.csr -config server.cnf

echo "==> Firmando el certificado de servidor con el CA..."
openssl x509 -req -in server.csr -CA CA.crt -CAkey CA.key -CAcreateserial \
    -out server.crt -days "$DAYS_SERVER" -sha256 \
    -extfile server.cnf -extensions req_ext

echo "==> Empaquetando server.pem (crt+key) para HAProxy..."
cat server.crt server.key > server.pem

echo "==> Listo. Archivos generados en $(pwd):"
ls -1 CA.crt CA.key server.crt server.csr server.key server.pem
