@echo off
title VISIOFLOW Orchestrator
color 0B

echo ===================================================
echo        VISIOFLOW - INICIO DEL SISTEMA (WINDOWS)
echo ===================================================
echo.

:: 1. Levantar el servidor de la camara en segundo plano
echo [1/3] Iniciando puente de hardware en Windows...
start /B python camara\camara_windows.py > nul 2>&1

:: Darle 3 segundos a la camara para calentar
timeout /t 3 /nobreak > nul

:: 2. Variables de entorno para Windows (redireccion por HTTP al host)
set CAMERA_SOURCE=http://host.docker.internal:5001/video
set CAMERA_DEVICE=/dev/null

:: 3. Logica Inteligente de Docker
echo [2/3] Verificando estado de la infraestructura...

:: Buscamos silenciosamente si el contenedor de Flask ya existe
docker ps -a --format "{{.Names}}" | findstr /C:"FlaskVisioflow" > nul

:: El comando anterior genera un "errorlevel 0" si lo encuentra, y "1" si no existe
if %errorlevel% equ 0 (
    echo [OK] Contenedores detectados. Actualizando y despertando sistema...
    docker compose up -d
) else (
    echo [INFO] Primera instalacion detectada. Construyendo desde cero...
    docker compose up --build -d
)

:: 4. Preparar e Iniciar Aplicacion Movil (Expo Go)
echo.
echo [3/3] Verificando y preparando la aplicacion movil (Expo Go)...

if not exist "%~dp0visioflow\node_modules" (
    echo [INFO] Primera clonacion detectada. Instalando dependencias npm en visioflow...
    cd /d "%~dp0visioflow"
    call npm install
    cd /d "%~dp0"
)

:: Detectar IP LAN
set "LAN_IP="
for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "$addresses = @(Get-NetIPAddress -InterfaceAlias 'Wi-Fi' -AddressFamily IPv4 -ErrorAction SilentlyContinue); if ($addresses.Count -gt 0) { [Console]::Write($addresses[0].IPAddress.Trim()) }"`) do set "LAN_IP=%%I"

if not defined LAN_IP (
    set "LAN_IP=127.0.0.1"
)

set "REACT_NATIVE_PACKAGER_HOSTNAME=%LAN_IP%"
set "EXPO_PUBLIC_API_BASE_URL=http://%LAN_IP%:5000"

echo.
echo ===================================================
echo [EXITO] ¡Sistema en linea!
echo.
echo - Puente de camara activo en: http://localhost:5001/video
echo - Stream VISIOFLOW (Flask) activo en: http://localhost:5000/video_feed
echo - API FastAPI activo en: http://localhost:8000
echo - API para Movil: %EXPO_PUBLIC_API_BASE_URL%
echo ===================================================
echo.
echo Lanzando servidor Expo Go en una ventana separada...

start "VisioFlow Mobile (Expo Go)" cmd /k "cd /d "%~dp0visioflow" && set REACT_NATIVE_PACKAGER_HOSTNAME=%LAN_IP%&& set EXPO_PUBLIC_API_BASE_URL=http://%LAN_IP%:5000&& npx expo start --lan --go"

pause