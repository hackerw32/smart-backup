@echo off
cd /d "%~dp0"
echo [1/2] Εγκατασταση απαραιτητων βιβλιοθηκων...
py -m pip install --upgrade pip
py -m pip install watchdog pyinstaller
if errorlevel 1 goto error
echo [2/2] Δημιουργια εκτελεσιμου...
py -m PyInstaller --noconfirm --clean --onefile --windowed --name "SmartBackup" --paths "%~dp0" --collect-submodules watchdog "%~dp0smart_backup.py"
if errorlevel 1 goto error
echo.
echo Ετοιμο! Το exe ειναι στο: %~dp0dist\SmartBackup.exe
pause
exit /b 0
:error
echo.
echo Η διαδικασια απετυχε. Δες τα μηνυματα πανω.
pause
exit /b 1
