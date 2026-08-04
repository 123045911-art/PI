@echo off
echo ===================================================
echo        VISIOFLOW - APAGADO DEL SISTEMA (WINDOWS)
echo ===================================================
echo.

echo [1/2] Pausando contenedores de Docker...
docker compose stop

echo [2/2] Cerrando solo las terminales de VisioFlow...
taskkill /F /FI "WINDOWTITLE eq VISIOFLOW - Camara*" /T > nul 2>&1
taskkill /F /FI "WINDOWTITLE eq VISIOFLOW - Docker*" /T > nul 2>&1
taskkill /F /FI "WINDOWTITLE eq VISIOFLOW - Android*" /T > nul 2>&1
taskkill /F /FI "WINDOWTITLE eq VisioFlow - API publica*" /T > nul 2>&1

echo.
echo ¡Sistema apagado correctamente!
pause
