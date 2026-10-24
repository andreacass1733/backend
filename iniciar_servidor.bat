@echo off
title Servidor Backend SOP
echo ==========================================================
echo    INICIANDO SERVIDOR BACKEND SOP (CRITERIOS ROTTERDAM)
echo ==========================================================

echo [1/3] Liberando puerto 8000 si estuviera ocupado por un proceso previo...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    taskkill /f /pid %%a >nul 2>&1
)

set PYTHON_BIN=python
if exist ".\venv\Scripts\python.exe" (
    set PYTHON_BIN=.\venv\Scripts\python.exe
)

echo [2/3] Entorno virtual: %PYTHON_BIN%
echo [3/3] Iniciando Uvicorn en http://127.0.0.1:8000...
%PYTHON_BIN% -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
pause
