# Πώς βγάζω νέα έκδοση

Σύντομος οδηγός για να κυκλοφορήσεις νέα έκδοση. Η εφαρμογή χρησιμοποιεί το
`VERSION` στο `smartbackup/constants.py` και το GitHub Releases για τον έλεγχο ενημερώσεων.

## 1. Ανέβασε την έκδοση

Άνοιξε το `smartbackup/constants.py` και άλλαξε το:

```python
VERSION = "1.0.1"   # από 1.0.0
```

> Το `VERSION` πρέπει να είναι **μεγαλύτερο** από την προηγούμενη έκδοση, αλλιώς
> η εφαρμογή θα νομίζει ότι είναι ενημερωμένη. Το tag μπορεί να έχει `v` μπροστά,
> π.χ. `v1.0.1`.

Μετά τρέξε τα tests (προαιρετικό αλλά συνιστάται):

```powershell
py -m compileall smartbackup smart_backup.py
```

## 2. Commit

```powershell
git add -A
git commit -m "Release v1.0.1"
git push origin main
```

## 3. Tag

```powershell
git tag v1.0.1
git push origin v1.0.1
```

## 4. Φτιάξε το .exe

Διπλό κλικ στο `build_exe.bat` (ή τρέξε):

```powershell
py -m pip install pyinstaller
py -m PyInstaller --noconfirm --clean --onefile --windowed --name "SmartBackup" --paths "." --collect-submodules watchdog "smart_backup.py"
```

Το αποτέλεσμα είναι στο `dist\SmartBackup.exe`.

## 5. Δημιούργησε το Release και ανέβασε το .exe

Αν το `gh` είναι στο PATH:

```powershell
gh release create v1.0.1 --title "Smart Backup v1.0.1" --notes "Τι άλλαξε..." "dist\SmartBackup.exe"
```

Αλλιώς χρησιμοποίησε την πλήρη διαδρομή:

```powershell
& "C:\Program Files\GitHub CLI\gh.exe" release create v1.0.1 --title "Smart Backup v1.0.1" --notes "Τι άλλαξε..." "dist\SmartBackup.exe"
```

Για να προσθέσεις/αντικαταστήσεις το exe σε υπάρχον release:

```powershell
gh release upload v1.0.1 "dist\SmartBackup.exe" --clobber
```

## 6. Έτοιμο

Οποιοσδήποτε τρέχει παλαιότερη έκδοση θα βλέπει «New version available: 1.0.1»
πατώντας **Settings... → Check for updates**, με σύνδεσμο λήψης το release.

## Σημειώσεις

- Οι ρυθμίσεις ζουν στο `%APPDATA%\SmartBackup\config.json`, οπότε **δεν χάνονται**
  όταν αντικατασταθεί το `.exe`.
- Το `gh` εγκαθίσταται με `winget install --id GitHub.cli` και μετά `gh auth login`.
- Μην κάνεις commit τα `config.json`, `*.log`, `dist/`, `build/` — είναι ήδη στο `.gitignore`.
