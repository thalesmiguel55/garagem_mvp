@echo off
chcp 65001 >nul
title Garagem MVP - 192.168.188.36:7070
cd /d "%~dp0"

echo.
echo  ========================================
echo   Sistema Garagem MVP
echo  ========================================
echo   URL:   http://192.168.188.36:7070/
echo   Admin: http://192.168.188.36:7070/admin
echo   QR:    static\qrcode.html
echo  ========================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo  Ambiente virtual nao encontrado.
    echo  Execute antes: python -m venv .venv
    echo  Depois: .venv\Scripts\pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0iniciar_servidor.ps1" -Port 7070 %*

if errorlevel 1 (
    echo.
    echo  Erro ao iniciar o servidor.
    pause
    exit /b 1
)