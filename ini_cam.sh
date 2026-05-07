#!/bin/bash

echo "==================================================="
echo "       VISIOFLOW - INICIO DEL SISTEMA (LINUX)      "
echo "==================================================="
echo

echo "[1/2] Detectando cámara..."

# Default fallback (suele ser la integrada si no hay otra)
CAMERA_DEVICE="/dev/video0" 
camera_found=false

# Buscar cámaras en /sys/class/video4linux
if [ -d "/sys/class/video4linux" ]; then
    for sys_cam in /sys/class/video4linux/video*; do
        if [ -e "$sys_cam/name" ]; then
            name=$(cat "$sys_cam/name" 2>/dev/null)
            dev_node="/dev/$(basename "$sys_cam")"
            
            # Ignorar dispositivos de metadatos
            if [[ "$name" == *"Metadata"* ]] || [[ "$name" == *"metadata"* ]]; then
                continue
            fi

            # Prioridad 1: Cámara USB (Webcam externa)
            if [[ "$name" == *"USB"* ]] || [[ "$name" == *"usb"* ]]; then
                CAMERA_DEVICE="$dev_node"
                echo "-> Cámara externa (USB) detectada: $name en $CAMERA_DEVICE"
                camera_found=true
                break
            fi
            
            # Prioridad 2: Cámara Integrada
            if [[ "$camera_found" == false ]]; then
                if [[ "$name" == *"Integrated"* ]] || [[ "$name" == *"Webcam"* ]] || [[ "$name" == *"Camera"* ]]; then
                    CAMERA_DEVICE="$dev_node"
                    camera_found=true
                fi
            fi
        fi
    done
fi

if [[ "$camera_found" == false ]]; then
    echo "-> No se detectó cámara externa por nombre, usando por defecto: $CAMERA_DEVICE"
else
    echo "-> Seleccionada para VisioFlow: $CAMERA_DEVICE"
fi

export CAMERA_DEVICE
export CAMERA_SOURCE=0  # Dentro de Docker siempre estará en /dev/video0 por el mapeo en el compose

echo
echo "[2/2] Verificando estado de la infraestructura de Docker..."

if docker ps -a --format '{{.Names}}' | grep -Eq "^FlaskVisioflow$"; then
    echo "[OK] Contenedores detectados. Despertando sistema rápidamente..."
    # Recrear el contenedor flask_service si la cámara ha cambiado
    # Hacemos up -d para asegurar que el mapeo de devices tome el nuevo CAMERA_DEVICE si cambió
    docker compose up -d
else
    echo "[INFO] Primera instalación detectada o contenedores no existen. Construyendo desde cero..."
    docker compose up --build -d
fi

echo
echo "==================================================="
echo "[EXITO] ¡Sistema en línea!"
echo
echo "- Cámara activa apuntando a: $CAMERA_DEVICE"
echo "- Dashboard VISIOFLOW (Laravel) activo en: http://localhost:8085"
echo "- Stream VISIOFLOW (Flask) activo en: http://localhost:5000/video"
echo "- API FastAPI activo en: http://localhost:8000"
echo "==================================================="
echo
