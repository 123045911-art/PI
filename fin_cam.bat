@echo off
echo Pausando contenedores de Docker
docker compose stop

echo Apagando puente de camara en Windows...
taskkill /F /IM python.exe /T > nul 2>&1

echo ¡Sistema apagado correctamente!
pause