@echo off
echo ========================================================
echo   Building Say It Desktop App (Release Executable)
echo ========================================================
cd /d "%~dp0"
call .venv\Scripts\python.exe scripts\build_executable.py
pause
