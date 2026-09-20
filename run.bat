@echo off
cd /d "%~dp0"
py "%~dp0smart_backup.py"
if errorlevel 1 pause
