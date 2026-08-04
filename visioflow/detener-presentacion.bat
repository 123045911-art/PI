@echo off
setlocal
title VisioFlow - Detener presentacion
echo Deteniendo los procesos que escuchan en los puertos 5000 y 8081...
powershell -NoProfile -Command "$ids = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -in 5000,8081 } | Select-Object -ExpandProperty OwningProcess -Unique; foreach ($processId in $ids) { Stop-Process -Id $processId -ErrorAction SilentlyContinue }"
echo Presentacion detenida.
endlocal
