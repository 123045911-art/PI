@echo off
title VISIOFLOW Orchestrator
color 0B

echo ===================================================
echo        VISIOFLOW - INICIO DEL SISTEMA
echo ===================================================
echo.

:: 1. Levantar el servidor de la camara en segundo plano
echo [1/2] Iniciando puente de hardware en Windows...
start /B python camara\camara_windows.py > nul 2>&1

:: Darle 3 segundos a la camara para calentar
timeout /t 3 /nobreak > nul

:: 2. Logica Inteligente de Docker
echo [2/2] Verificando estado de la infraestructura...

:: Buscamos silenciosamente si el contenedor de Flask ya existe
docker ps -a --format "{{.Names}}" | findstr /C:"FlaskVisioflow" > nul

:: El comando anterior genera un "errorlevel 0" si lo encuentra, y "1" si no existe
if %errorlevel% equ 0 (
    echo [OK] Contenedores detectados. Despertando sistema rapidamente...
    docker compose start
) else (
    echo [INFO] Primera instalacion detectada. Construyendo desde cero...
    docker compose up --build -d
)

echo.
echo ===================================================
echo [EXITO] ¡Sistema en linea!
echo.
echo - Camara activa en puerto 5001
echo - Dashboard VISIOFLOW activo en: http://localhost:5000
echo - Flask VISIOFLOW activo en: http://localhost:5001
echo ===================================================
echo.
pause