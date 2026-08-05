@echo off
setlocal
cd /d "%~dp0"
title VisioFlow - Expo Go

if not exist "package.json" (
  echo [ERROR] No se encontro package.json en %CD%.
  pause
  exit /b 1
)
if not exist "node_modules\expo\bin\cli" (
  echo Instalando dependencias Android por primera vez...
  call npm install
  if errorlevel 1 (
    echo [ERROR] npm install fallo.
    pause
    exit /b 1
  )
)

echo.
echo  ==========================================
echo           VISIOFLOW - EXPO GO
echo  ==========================================
echo.
echo  [1] LAN         - Rapido, celular y PC en el mismo Wi-Fi (API local)
echo  [2] Tunel       - Funciona entre redes, puede tardar mas (API local)
echo  [3] Produccion  - Usa el backend ya desplegado en AWS
echo.
choice /C 123 /N /M "Elige 1, 2 o 3: "

if errorlevel 3 goto production
if errorlevel 2 goto tunnel

:lan
echo.
set "LAN_IP="
for /f "usebackq delims=" %%I in (`%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -Command "$addresses = @(Get-NetIPAddress -InterfaceAlias 'Wi-Fi' -AddressFamily IPv4 -ErrorAction SilentlyContinue); if ($addresses.Count -gt 0) { [Console]::Write($addresses[0].IPAddress.Trim()) }"`) do set "LAN_IP=%%I"
if not defined LAN_IP (
  echo [ERROR] No se pudo detectar una IP LAN con puerta de enlace.
  echo Conecta la PC al Wi-Fi y vuelve a ejecutar este archivo.
  goto end
)
set "REACT_NATIVE_PACKAGER_HOSTNAME=%LAN_IP%"
set "EXPO_PUBLIC_API_BASE_URL=http://%LAN_IP%:8000"
echo Iniciando VisioFlow por LAN en %LAN_IP%...
echo Android debe mostrar exp://%LAN_IP%:8081 o un puerto equivalente.
echo La linea Web is waiting on localhost es normal y solo corresponde a la PC.
echo API para Android: %EXPO_PUBLIC_API_BASE_URL%
echo Escanea el QR mostrado con Expo Go.
echo.
call npx -y node@22 node_modules/expo/bin/cli start --lan --go --clear
goto end

:tunnel
echo.
echo Iniciando tunel publico para FastAPI...
if exist ".api-tunnel-url" del /q ".api-tunnel-url"
start "VisioFlow - API publica" cmd /k "cd /d ""%~dp0"" && node scripts\start-api-tunnel.js"
for /L %%N in (1,1,45) do (
  if exist ".api-tunnel-url" goto api_tunnel_ready
  timeout /t 1 /nobreak >nul
)
echo [ERROR] El tunel de la API no entrego una URL.
echo Revisa la terminal "VisioFlow - API publica".
goto end

:api_tunnel_ready
set /p API_TUNNEL_URL=<".api-tunnel-url"
set "EXPO_PUBLIC_API_BASE_URL=%API_TUNNEL_URL%"
echo API publica: %EXPO_PUBLIC_API_BASE_URL%
echo Iniciando el tunel de Expo. Escanea el QR cuando aparezca.
echo.
call npx -y node@22 node_modules/expo/bin/cli start --tunnel --go --clear
goto end

:production
echo.
echo Usando el backend de produccion en AWS (18-223-97-60.sslip.io).
set "EXPO_PUBLIC_API_BASE_URL=https://18-223-97-60.sslip.io:8080"
set "LAN_IP="
for /f "usebackq delims=" %%I in (`%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -Command "$addresses = @(Get-NetIPAddress -InterfaceAlias 'Wi-Fi' -AddressFamily IPv4 -ErrorAction SilentlyContinue); if ($addresses.Count -gt 0) { [Console]::Write($addresses[0].IPAddress.Trim()) }"`) do set "LAN_IP=%%I"
if not defined LAN_IP (
  echo [ERROR] No se pudo detectar una IP LAN con puerta de enlace.
  echo Conecta la PC al Wi-Fi y vuelve a ejecutar este archivo.
  goto end
)
set "REACT_NATIVE_PACKAGER_HOSTNAME=%LAN_IP%"
echo Celular y PC deben estar en el mismo Wi-Fi para cargar la app (%LAN_IP%).
echo API de produccion: %EXPO_PUBLIC_API_BASE_URL%
echo Escanea el QR mostrado con Expo Go.
echo.
call npx -y node@22 node_modules/expo/bin/cli start --lan --go --clear
goto end

:end
echo.
echo El servidor se detuvo. Presiona una tecla para cerrar.
pause >nul
endlocal
