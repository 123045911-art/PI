@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title VISIOFLOW - Inicio completo
color 0B

echo ===================================================
echo       VISIOFLOW - INICIO COMPLETO Y VISIBLE
echo ===================================================
echo.

docker info >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Docker Desktop no esta iniciado.
  echo Abre Docker Desktop, espera a que indique que esta listo y repite.
  pause
  exit /b 1
)

if not exist "%~dp0visioflow\package.json" (
  echo Preparando el repositorio Android...
  git submodule update --init --recursive
  if errorlevel 1 (
    echo [ERROR] No se pudo descargar el submodulo visioflow.
    pause
    exit /b 1
  )
)

"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -Command "try { $h=Invoke-RestMethod 'http://127.0.0.1:5001/health' -TimeoutSec 2; if($h.camera_open){exit 0}else{exit 1} } catch { exit 1 }"
if errorlevel 1 (
  echo [1/3] Abriendo puente de camara...
  start "VISIOFLOW - Camara" cmd /k "cd /d ""%~dp0"" && call ini_cam.bat"
) else (
  echo [1/3] Puente de camara ya activo.
)

echo [2/3] Abriendo Docker Compose con logs visibles...
start "VISIOFLOW - Docker" cmd /k "cd /d ""%~dp0"" && docker compose up --build"

echo Esperando FastAPI y Flask...
for /L %%N in (1,1,120) do (
  "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -Command "try { Invoke-RestMethod 'http://127.0.0.1:8000/health' -TimeoutSec 2|Out-Null; Invoke-RestMethod 'http://127.0.0.1:5000/health' -TimeoutSec 2|Out-Null; exit 0 } catch { exit 1 }"
  if not errorlevel 1 goto services_ready
  timeout /t 1 /nobreak >nul
)
echo [ERROR] Los servicios no respondieron. Revisa la terminal Docker.
pause
exit /b 1

:services_ready
echo [OK] Web: http://127.0.0.1:5000
echo [OK] API: http://127.0.0.1:8000
echo [3/3] Abriendo Android/Expo en otra terminal...
start "VISIOFLOW - Android" cmd /k "cd /d ""%~dp0visioflow"" && call iniciar-visioflow.bat"
echo.
echo Todo se abrio en terminales visibles.
echo En Android elige LAN si el celular esta en el mismo Wi-Fi.
echo Elige Tunel si esta en otra red; ahora publica Expo Y FastAPI.
pause
