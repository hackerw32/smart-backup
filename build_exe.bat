@echo off
cd /d "%~dp0"
echo [1/2] Installing required packages...
py -m pip install --upgrade pip
py -m pip install watchdog pyinstaller
if errorlevel 1 goto error
echo [2/2] Building executable...
py -m PyInstaller --noconfirm --clean --onefile --windowed --name "SmartBackup" --paths "." --collect-submodules watchdog "smart_backup.py"
if errorlevel 1 goto error
echo.
echo Done! The exe is in: dist\SmartBackup.exe
pause
exit /b 0
:error
echo.
echo Build failed. See the messages above.
pause
exit /b 1
