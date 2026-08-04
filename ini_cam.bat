@echo off
setlocal
title VISIOFLOW - Puente de camara
color 0B

echo ===================================================
echo        VISIOFLOW - PUENTE DE CAMARA WINDOWS
echo ===================================================
echo.

set "CAMERA_PYTHON="
if exist "%~dp0contador_personas_flask\.venv\Scripts\python.exe" set "CAMERA_PYTHON=%~dp0contador_personas_flask\.venv\Scripts\python.exe"
if not defined CAMERA_PYTHON for /f "delims=" %%P in ('where python 2^>nul') do if not defined CAMERA_PYTHON set "CAMERA_PYTHON=%%P"

if not defined CAMERA_PYTHON (
    echo [ERROR] No se encontro Python.
    pause
    exit /b 1
)

echo [1/2] Python seleccionado: %CAMERA_PYTHON%
"%CAMERA_PYTHON%" -c "import cv2, flask" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Instalando Flask y OpenCV...
    "%CAMERA_PYTHON%" -m pip install -r "%~dp0camara\requirements.txt"
    if errorlevel 1 (
        echo [ERROR] No fue posible instalar dependencias.
        pause
        exit /b 1
    )
)

echo [2/2] Iniciando el puente en esta terminal...
echo [OK] Deja abierta esta terminal. Video: http://127.0.0.1:5001/video
"%CAMERA_PYTHON%" "%~dp0camara\camara_windows.py"
