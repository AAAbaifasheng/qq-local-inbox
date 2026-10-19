@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Virtual environment missing. Run install.ps1 first.
  pause
  exit /b 1
)
.venv\Scripts\python.exe -m src.main
if errorlevel 1 pause
