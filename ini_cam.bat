@echo off
title VISIOFLOW Orchestrator
color 0B

echo ===================================================
echo        VISIOFLOW - INICIO DEL SISTEMA (UPQ)
echo ===================================================
echo.

:: 1. Levantar el servidor de la camara en segundo plano
echo [1/2] Iniciando puente de hardware en Windows...
start /B py camara\camara_windows.py > nul 2>&1

:: Darle 5 segundos a la camara para calentar y al servidor para iniciar
timeout /t 5 /nobreak > nul

:: 2. Levantar la infraestructura de Docker
echo [2/2] Despertando entorno Linux (Docker Compose)...
docker compose up --build -d

echo.
echo ===================================================
echo [EXITO] ¡Sistema en linea, Ali!
echo.
echo - Camara activa en: http://localhost:5001/video
echo - Dashboard VISIOFLOW activo en: http://localhost:5000
echo ===================================================
echo.
pause