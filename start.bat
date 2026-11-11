@echo off
chcp 65001 >nul
title GitHub Activity Generator - kotmir
cd /d "%~dp0"
echo.
echo  [RU] Запуск GitHub Activity Generator... Не кликайте мышью в этом окне.
echo  [EN] Starting GitHub Activity Generator... Do not click inside this window.
echo.
where python >nul 2>nul
if %errorlevel%==0 (
    python run.py %*
    goto end
)
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 run.py %*
    goto end
)
echo [RU] Python не найден. Установите Python 3.8+ с https://www.python.org/downloads/
echo [EN] Python not found. Install Python 3.8+ from https://www.python.org/downloads/
:end
pause
