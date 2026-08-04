@echo off
echo ===================================================
echo        VISIOFLOW - APAGADO DEL SISTEMA (WINDOWS)
echo ===================================================
echo.

echo [1/2] Pausando contenedores de Docker...
docker compose stop

echo [2/2] Apagando puente de camara y servidor movil...
taskkill /F /IM python.exe /T > nul 2>&1
taskkill /F /FI "WINDOWTITLE eq VisioFlow Mobile*" /T > nul 2>&1

echo.
echo ¡Sistema apagado correctamente!
pause