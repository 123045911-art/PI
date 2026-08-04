#!/bin/bash

echo "==================================================="
echo "       VISIOFLOW - INICIO DEL SISTEMA (LINUX)      "
echo "==================================================="
echo

echo "[1/4] Detectando cámara..."

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
    if [ -c "$CAMERA_DEVICE" ]; then
        echo "-> No se detectó cámara por nombre, usando por defecto: $CAMERA_DEVICE"
    else
        echo "-> ADVERTENCIA: No se encontró ningún dispositivo físico de cámara (/dev/video0)."
        echo "-> Usando /dev/null como fallback seguro para Docker."
        CAMERA_DEVICE="/dev/null"
    fi
else
    echo "-> Seleccionada para VisioFlow: $CAMERA_DEVICE"
fi

export CAMERA_DEVICE
export CAMERA_SOURCE=0  # Dentro de Docker siempre estará en /dev/video0 por el mapeo en el compose

echo
echo "[2/4] Verificando estado de la infraestructura de Docker..."

# Verificar si el demonio de Docker está corriendo
if ! docker info >/dev/null 2>&1; then
    echo
    echo "[ERROR] El servicio de Docker no está iniciado."
    echo "Ejecuta el siguiente comando para iniciar Docker:"
    echo "    sudo systemctl start docker"
    echo
    exit 1
fi

if docker ps -a --format '{{.Names}}' | grep -Eq "^FlaskVisioflow$"; then
    echo "[OK] Contenedores detectados. Despertando sistema rápidamente..."
    docker compose up -d || { echo "[ERROR] Falló el arranque de Docker Compose."; exit 1; }
else
    echo "[INFO] Primera instalación detectada o contenedores no existen. Construyendo desde cero..."
    docker compose up --build -d || { echo "[ERROR] Falló la construcción de Docker Compose."; exit 1; }
fi

echo
echo "[3/4] Verificando entorno de Node.js y aplicación móvil (visioflow)..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MOBILE_DIR="$SCRIPT_DIR/visioflow"

if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
    echo "[ADVERTENCIA] Node.js o npm no están instalados en el sistema principal."
    echo "El backend (Flask + PostgreSQL + FastAPI) está corriendo en Docker."
    echo "Para correr la app móvil Expo Go, instala Node.js (v18+) e intenta de nuevo."
    echo "  sudo apt update && sudo apt install -y nodejs npm"
    exit 1
fi

if [ -d "$MOBILE_DIR" ]; then
    if [ ! -d "$MOBILE_DIR/node_modules" ]; then
        echo "[INFO] Instalando dependencias de Node en visioflow (primera ejecución)..."
        (cd "$MOBILE_DIR" && npm install) || { echo "[ERROR] Falló la instalación de dependencias npm."; exit 1; }
    fi
else
    echo "[ERROR] No se encontró el directorio de la aplicación móvil en $MOBILE_DIR"
    exit 1
fi

# Detectar IP LAN para Expo y conectar con Flask
LAN_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
if [ -z "$LAN_IP" ]; then
    LAN_IP=$(ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}')
fi
[ -z "$LAN_IP" ] && LAN_IP="127.0.0.1"

export REACT_NATIVE_PACKAGER_HOSTNAME="$LAN_IP"
export EXPO_PUBLIC_API_BASE_URL="http://$LAN_IP:5000"

# Crear/actualizar archivo .env dentro de visioflow para garantizar configuración en Expo
cat <<EOF > "$MOBILE_DIR/.env"
EXPO_PUBLIC_API_BASE_URL=http://$LAN_IP:5000
REACT_NATIVE_PACKAGER_HOSTNAME=$LAN_IP
EOF

echo "[OK] Archivo de entorno visioflow/.env actualizado con EXPO_PUBLIC_API_BASE_URL=http://$LAN_IP:5000"

echo
echo "[4/4] Lanzando aplicación móvil VisioFlow (Expo Go)..."
echo "==================================================="
echo "[ÉXITO] ¡Infraestructura Backend y API en línea!"
echo
echo "- Cámara activa apuntando a: $CAMERA_DEVICE"
echo "- Stream VISIOFLOW (Flask) activo en: http://localhost:5000/video_feed"
echo "- API FastAPI activo en: http://localhost:8000"
echo "- Servidor API Móvil asignado a: $EXPO_PUBLIC_API_BASE_URL"
echo "==================================================="
echo
echo "Iniciando servidor de desarrollo Expo Go..."
echo "Escanea el código QR mostrado a continuación con la app Expo Go:"
echo

cd "$MOBILE_DIR"
exec npx expo start --lan --go
