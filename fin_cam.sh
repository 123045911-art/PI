#!/bin/bash

echo "==================================================="
echo "       VISIOFLOW - APAGADO DEL SISTEMA (LINUX)     "
echo "==================================================="
echo

echo "[1/3] Deteniendo contenedores de Docker (esto puede tardar unos segundos)..."
docker compose stop

echo "[2/3] Deteniendo servidor de desarrollo de la aplicación móvil (Expo)..."
pkill -f "expo-cli" > /dev/null 2>&1 || true
pkill -f "metro" > /dev/null 2>&1 || true
pkill -f "expo start" > /dev/null 2>&1 || true

echo "[3/3] Asegurando liberación de recursos..."
pkill -f "python3" > /dev/null 2>&1 || true

echo
echo "==================================================="
echo "¡Sistema apagado y recursos liberados correctamente!"
echo "==================================================="
echo
