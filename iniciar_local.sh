#!/bin/bash
# =============================================================================
# iniciar_local.sh — Levanta el sistema VisioFlow completo en Linux
#
# Arquitectura:
#   Terminal 1 (esta): Docker (PostgreSQL + FastAPI)
#   Terminal 2 (nueva): Flask local con webcam nativa
#   Resultado:          Instrucciones para lanzar Expo en otra terminal
#
# Requisitos:
#   - Docker y docker compose funcionando
#   - Python 3.10+ instalado
#   - Webcam conectada
# =============================================================================
set -e

cd "$(dirname "$0")"
SCRIPT_DIR="$(pwd)"

echo
echo "==================================================================="
echo "     VISIOFLOW — ARRANQUE LOCAL COMPLETO (Linux)"
echo "==================================================================="
echo

# ─── Paso 1: Entorno virtual Python ──────────────────────────────────────────

VENV_DIR="$SCRIPT_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "[1/6] Creando entorno virtual Python..."
    python3 -m venv "$VENV_DIR"
    echo "  -> Instalando dependencias (esto puede tardar la primera vez)..."
    "$VENV_DIR/bin/pip" install --upgrade pip -q
    "$VENV_DIR/bin/pip" install -r contador_personas_flask/requirements.txt -q
    echo "  -> Entorno virtual creado en $VENV_DIR"
else
    echo "[1/6] Entorno virtual encontrado en $VENV_DIR"
fi

# ─── Paso 2: Autodetección de cámara ─────────────────────────────────────────

echo "[2/6] Detectando cámara..."

# Capturar la ÚLTIMA línea de stdout (el índice numérico)
DETECT_OUTPUT=$("$VENV_DIR/bin/python" detect_camera.py 2>&1) || {
    echo "$DETECT_OUTPUT"
    echo
    echo "ERROR: No se encontró ninguna cámara funcional."
    echo "Conecta una webcam y vuelve a ejecutar este script."
    exit 1
}
echo "$DETECT_OUTPUT" | head -n -1  # Imprimir las líneas informativas
CAMERA_INDEX=$(echo "$DETECT_OUTPUT" | tail -n 1)

if ! [[ "$CAMERA_INDEX" =~ ^[0-3]$ ]]; then
    echo "ERROR: detect_camera.py no retornó un índice válido: '$CAMERA_INDEX'"
    exit 1
fi

echo "  -> Cámara seleccionada: índice $CAMERA_INDEX"

# ─── Paso 3: Detectar IP LAN ─────────────────────────────────────────────────

echo "[3/6] Detectando IP de red local..."

LAN_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
if [ -z "$LAN_IP" ]; then
    LAN_IP=$(ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}')
fi
if [ -z "$LAN_IP" ]; then
    LAN_IP="127.0.0.1"
    echo "  -> ADVERTENCIA: No se detectó IP LAN. Usando 127.0.0.1 (solo funciona local)."
else
    echo "  -> IP LAN detectada: $LAN_IP"
fi

# ─── Paso 4: Docker (solo BD + API) ──────────────────────────────────────────

echo "[4/6] Preparando infraestructura Docker..."

# Detener el contenedor Flask de Docker (libera el puerto 5000)
if docker ps --format '{{.Names}}' | grep -q "^FlaskVisioflow$"; then
    echo "  -> Deteniendo FlaskVisioflow de Docker (Flask correrá local)..."
    docker stop FlaskVisioflow >/dev/null 2>&1 || true
fi

# Asegurar que los demás contenedores estén corriendo
CONTAINERS_NEEDED="PostgreSqlVisioflow FastAPIVisioflow"
ALL_UP=true
for container in $CONTAINERS_NEEDED; do
    if ! docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
        ALL_UP=false
        break
    fi
done

if [ "$ALL_UP" = true ]; then
    echo "  -> Contenedores de infraestructura ya están corriendo."
else
    echo "  -> Levantando contenedores de infraestructura..."
    docker compose up -d db api 2>/dev/null || docker compose up -d 2>/dev/null
fi

# Esperar a que FastAPI esté healthy
echo "  -> Esperando a que FastAPI esté listo..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
        echo "  -> FastAPI respondiendo correctamente."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "  -> ADVERTENCIA: FastAPI no respondió tras 30 intentos. Continuando igualmente."
    fi
    sleep 1
done

# ─── Paso 5: Cargar variables de .env ────────────────────────────────────────

echo "[5/6] Cargando variables de entorno..."

# Exportar variables del .env (ignorar comentarios y líneas vacías)
set -a
while IFS='=' read -r key value; do
    # Ignorar comentarios y líneas vacías
    [[ "$key" =~ ^#.*$ ]] && continue
    [[ -z "$key" ]] && continue
    # Quitar espacios
    key=$(echo "$key" | xargs)
    value=$(echo "$value" | xargs)
    [ -n "$key" ] && export "$key=$value"
done < "$SCRIPT_DIR/.env"
set +a

# Sobreescribir con los valores específicos para ejecución local
export APP_ENV=local
export LOCAL_DEMO_AUTH=1
export SENSOR_MODE=monocular
export VISIOFLOW_START_BACKGROUND=1
export CAMERA_SOURCE="$CAMERA_INDEX"
export CAMERA_ID=dell-wb7022
export FLASK_HOST=0.0.0.0
export FLASK_PORT=5000
export FLASK_DEBUG=0

# API del backend FastAPI dentro de Docker
export VISIOFLOW_API_BASE_URL=http://localhost:8000
export API_BASE_URL=http://localhost:8000

echo "  -> Variables configuradas:"
echo "     APP_ENV=$APP_ENV"
echo "     CAMERA_SOURCE=$CAMERA_SOURCE"
echo "     CAMERA_ID=$CAMERA_ID"
echo "     SENSOR_MODE=$SENSOR_MODE"
echo "     FLASK_HOST=$FLASK_HOST:$FLASK_PORT"

# ─── Paso 6: Lanzar Flask localmente ─────────────────────────────────────────

echo "[6/6] Iniciando Flask localmente..."
echo
echo "==================================================================="
echo " FLASK arrancando en http://$LAN_IP:5000"
echo "==================================================================="
echo
echo " Endpoints útiles:"
echo "   Health:    http://$LAN_IP:5000/health"
echo "   Video:     http://$LAN_IP:5000/video_feed"
echo "   Sites:     http://$LAN_IP:5000/api/v1/sites"
echo "   Bootstrap: http://$LAN_IP:5000/api/v1/sites/pasillo-real/bootstrap"
echo "   Conteos:   http://$LAN_IP:5000/api/v1/sites/pasillo-real/area-state"
echo
echo "==================================================================="
echo " Para lanzar EXPO (en OTRA terminal):"
echo "==================================================================="
echo
echo "   cd $SCRIPT_DIR/visioflow"
echo "   EXPO_PUBLIC_API_BASE_URL=http://$LAN_IP:5000 \\"
echo "   REACT_NATIVE_PACKAGER_HOSTNAME=$LAN_IP \\"
echo "   npx expo start --lan --clear"
echo
echo "==================================================================="
echo " Presiona Ctrl+C para detener Flask."
echo "==================================================================="
echo

cd "$SCRIPT_DIR/contador_personas_flask"
exec "$VENV_DIR/bin/python" run.py
