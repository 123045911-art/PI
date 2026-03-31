@echo off
echo Apagando contenedores de Docker...
docker compose down

echo Apagando puente de camara en Windows...
taskkill /F /IM python.exe /T > nul 2>&1

echo ¡Sistema apagado correctamente!
pause