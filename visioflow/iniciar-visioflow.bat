@echo off
setlocal
cd /d "%~dp0"
title VisioFlow - Expo Go

echo.
echo  ==========================================
echo           VISIOFLOW - EXPO GO
echo  ==========================================
echo.
echo  [1] LAN    - Rapido, celular y PC en el mismo Wi-Fi
echo  [2] Tunel  - Funciona entre redes, puede tardar mas
echo.
choice /C 12 /N /M "Elige 1 o 2: "

if errorlevel 2 goto tunnel

:lan
echo.
set "LAN_IP="
for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "$addresses = @(Get-NetIPAddress -InterfaceAlias 'Wi-Fi' -AddressFamily IPv4 -ErrorAction SilentlyContinue); if ($addresses.Count -gt 0) { [Console]::Write($addresses[0].IPAddress.Trim()) }"`) do set "LAN_IP=%%I"
if not defined LAN_IP (
  echo [ERROR] No se pudo detectar una IP LAN con puerta de enlace.
  echo Conecta la PC al Wi-Fi y vuelve a ejecutar este archivo.
  goto end
)
set "REACT_NATIVE_PACKAGER_HOSTNAME=%LAN_IP%"
set "EXPO_PUBLIC_API_BASE_URL=http://%LAN_IP%:5000"
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
echo Iniciando VisioFlow con tunel publico...
echo Espera a que aparezca "Tunnel ready" y escanea el QR.
echo IMPORTANTE: el tunel publica Metro, pero no publica la API Flask.
echo.
call npx -y node@22 node_modules/expo/bin/cli start --tunnel --go
goto end

:end
echo.
echo El servidor se detuvo. Presiona una tecla para cerrar.
pause >nul
endlocal
