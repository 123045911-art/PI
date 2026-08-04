#!/bin/bash

# Cambiar al directorio del script
cd "$(dirname "$0")"

echo
echo " =========================================="
echo "        VISIOFLOW - EXPO GO (LINUX)       "
echo " =========================================="
echo
echo " [1] LAN    - Rapido, celular y PC en el mismo Wi-Fi"
echo " [2] Tunel  - Funciona entre redes, puede tardar mas"
echo

read -p "Elige 1 o 2: " opcion

case $opcion in
    2)
        echo
        echo "Iniciando VisioFlow con tunel publico..."
        echo "Espera a que aparezca \"Tunnel ready\" y escanea el QR."
        echo
        npx expo start --tunnel --go
        ;;
    1|*)
        echo
        echo "Iniciando VisioFlow por LAN..."
        echo "Escanea el QR mostrado con Expo Go."
        echo
        npx expo start --lan --go
        ;;
esac

echo
echo "El servidor se detuvo."
read -n 1 -s -r -p "Presiona cualquier tecla para salir..."
echo
