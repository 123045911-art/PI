#!/bin/bash

echo "==================================================="
echo "       VISIOFLOW - APAGADO DEL SISTEMA (LINUX)     "
echo "==================================================="
echo

echo "[1/2] Deteniendo contenedores de Docker (esto puede tardar unos segundos)..."
docker compose stop

echo "[2/2] Asegurando liberación de recursos..."
# En caso de que haya algún proceso de python local huérfano (opcional)
pkill -f "python3" > /dev/null 2>&1

echo
echo "==================================================="
echo "¡Sistema apagado y recursos liberados correctamente!"
echo "==================================================="
echo
