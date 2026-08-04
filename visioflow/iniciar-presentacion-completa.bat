@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title VisioFlow - Presentacion completa

set "FRONTEND_DIR=%~dp0"
set "FLASK_DIR=%~dp0..\PI\contador_personas_flask"

if not exist "%FLASK_DIR%\run.py" (
  echo [ERROR] No se encontro el modulo Flask en:
  echo %FLASK_DIR%
  pause
  exit /b 1
)

where python >nul 2>nul || (
  echo [ERROR] Python no esta disponible en PATH.
  pause
  exit /b 1
)
where node >nul 2>nul || (
  echo [ERROR] Node.js no esta disponible en PATH.
  pause
  exit /b 1
)

for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "$profile = Get-NetConnectionProfile | Where-Object { $_.IPv4Connectivity -eq 'Internet' } | Select-Object -First 1; if ($profile) { Get-NetIPAddress -InterfaceIndex $profile.InterfaceIndex -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '169.254.*' } | Select-Object -First 1 -ExpandProperty IPAddress }"`) do set "LAN_IP=%%I"
if not defined LAN_IP set "LAN_IP=127.0.0.1"

echo.
echo  ==================================================
echo       VISIOFLOW - PRUEBA INTEGRAL DEL PASILLO
echo  ==================================================
echo  PC/API: http://%LAN_IP%:5000
echo  Android y PC deben estar en el mismo Wi-Fi.
echo.

powershell -NoProfile -Command "try { Invoke-RestMethod 'http://127.0.0.1:5000/health' -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
if errorlevel 1 (
  echo [1/3] Iniciando vision Flask y camara Dell...
  start "VisioFlow - Vision Flask" /D "%FLASK_DIR%" cmd /k "set FLASK_SECRET_KEY=presentacion-local-2026-visioflow&& set APP_ENV=local&& set LOCAL_DEMO_AUTH=1&& set CAMERA_SOURCE=0&& set SENSOR_MODE=monocular&& set CAMERA_ID=dell-wb7022&& set API_RATE_LIMIT_REQUESTS=80&& set API_GLOBAL_RATE_LIMIT_REQUESTS=1200&& set API_RATE_LIMIT_WINDOW_SECONDS=10&& set MAX_MJPEG_STREAMS=4&& set MAX_MJPEG_STREAMS_PER_USER=1&& set CHARUCO_SQUARE_LENGTH_METERS=0.035&& set CHARUCO_MARKER_LENGTH_METERS=0.0175&& set CHARUCO_MIN_CAPTURES=5&& set VISIOFLOW_START_BACKGROUND=1&& set FLASK_DEBUG=0&& python run.py"
) else (
  echo [1/3] Flask ya estaba activo.
)

echo [2/3] Esperando que la API responda...
for /L %%N in (1,1,90) do (
  powershell -NoProfile -Command "try { $health = Invoke-RestMethod 'http://127.0.0.1:5000/health' -TimeoutSec 2; if ($health.status -eq 'ok') { exit 0 }; exit 1 } catch { exit 1 }"
  if not errorlevel 1 goto flask_ready
  timeout /t 1 /nobreak >nul
)
echo [ERROR] Flask no respondio en 90 segundos. Revisa la ventana Vision Flask.
pause
exit /b 1

:flask_ready
echo [2/3] API lista. Sitios: Mi pasillo y Sitio simulado.
set "EXPO_PUBLIC_API_BASE_URL=http://%LAN_IP%:5000"
set "REACT_NATIVE_PACKAGER_HOSTNAME=%LAN_IP%"
set "EXPO_NO_DEPENDENCY_VALIDATION=1"

if not exist "%FRONTEND_DIR%node_modules\expo\bin\cli" (
  echo Instalando dependencias del frontend por primera vez...
  call npm install
  if errorlevel 1 (
    echo [ERROR] npm install fallo.
    pause
    exit /b 1
  )
)

echo [3/3] Iniciando Expo Go por LAN...
echo En Expo Go abre la direccion que muestre Metro o escanea el QR.
echo Para terminar Expo usa Ctrl+C. Flask queda en su ventana independiente.
echo.
call npx -y node@22 node_modules/expo/bin/cli start --lan --go --clear

endlocal
