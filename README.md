# Smart Backup

Ένα ελαφρύ, δωρεάν εργαλείο backup για Windows με γραφικό περιβάλλον (Python + Tkinter).
Κρατά αντίγραφο των φακέλων σου σε πραγματικό χρόνο ή περιοδικά, με **καλάθι διαγραφών**
ώστε ό,τι σβήνεις από την πηγή να μη χάνεται.

## Βασικά χαρακτηριστικά

- **Πολλαπλές εργασίες (tasks)**: κάθε task έχει δική του πηγή, προορισμό, κανόνες και πρόγραμμα.
- **Real-time συγχρονισμός** με `watchdog` ή **περιοδικός** (κάθε X λεπτά/ώρες) ή **μόνο στην έναρξη**.
- **Κανόνες ανά φάκελο**:
  - `Normal (real time)` – κανονικός συγχρονισμός
  - `Skip - no backup` – αγνοείται (και καθαρίζεται από το backup στο επόμενο sync)
  - `Backup but no trash` – backup, αλλά οι διαγραφές σβήνονται οριστικά
  - `Periodic only` – μόνο στον περιοδικό/χειροκίνητο έλεγχο
  - `Periodic only and no trash` – συνδυασμός των δύο
- **Καλάθι διαγραφών**: τα διαγραμμένα αρχεία μεταφέρονται εκεί (με τη διαδρομή τους ή χύμα),
  με αυτόματη μετονομασία `dsn1`, `dsn2`, … σε συγκρούσεις ονόματος.
- **Ομαδοποιημένες αποτυχίες**: κατηγοριοποιημένα σφάλματα με δυνατότητα αντιγραφής/αποθήκευσης σε log.
- **Δίγλωσσο UI**: English / Ελληνικά (default English).
- **Έλεγχος ενημερώσεων** μέσω GitHub Releases.

## Απαιτήσεις

- Windows, Python 3.11+ (δοκιμασμένο σε 3.14)
- `watchdog`

```powershell
py -m pip install -r requirements.txt
```

## Εκτέλεση

```powershell
py smart_backup.py
```

ή διπλό κλικ στο `run.bat`.

## Δημιουργία .exe

Διπλό κλικ στο `build_exe.bat` — παράγει `dist\SmartBackup.exe`.

## Πού αποθηκεύονται οι ρυθμίσεις

Στο `%APPDATA%\SmartBackup\config.json` (και το log στο ίδιο folder). Έτσι **δεν χάνονται**
όταν αντικαταστήσεις το .exe με νέα έκδοση.

## Δομή κώδικα

```
smart_backup.py          # entry point
smartbackup/
  constants.py           # σταθερές, paths, έκδοση
  config.py              # Job/Rule, φόρτωση/αποθήκευση
  engine.py              # πυρήνας συγχρονισμού
  manager.py             # διαχείριση engines ανά task
  updates.py             # έλεγχος ενημερώσεων
  i18n.py                # μεταφράσεις
  ui/                    # app, wizard, taskview, settings, failures
```

## Νέα έκδοση

Οδηγός βήμα-βήμα: [RELEASING.md](RELEASING.md).

## Άδεια

MIT — δες [LICENSE](LICENSE).
