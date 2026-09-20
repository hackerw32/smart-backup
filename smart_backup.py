"""Smart Backup - σημείο εκκίνησης της εφαρμογής.

Η λογική βρίσκεται στο πακέτο ``smartbackup`` (constants, config, engine,
manager, ui). Αυτό το αρχείο απλώς ξεκινά το γραφικό περιβάλλον.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
from tkinter import messagebox

from smartbackup import (
    APP_DIR,
    APP_NAME,
    CONFIG_PATH,
    DEFAULT_DELETED_DIRNAME,
    LOGGER,
    LOG_PATH,
    MODE_IGNORE,
    MODE_NORMAL,
    MODE_NO_RECYCLE,
    MODE_PERIODIC,
    MODE_PERIODIC_NO_RECYCLE,
    RULE_MODES,
    VERSION,
    AppConfig,
    BackupEngine,
    FailuresDialog,
    Job,
    JobManager,
    JobWizard,
    Rule,
    SmartBackupApp,
    classify_error,
    load_config,
    save_config,
    setup_logging,
)
from smartbackup.engine import HAVE_WATCHDOG
from smartbackup import config, constants, engine, manager, updates  # noqa: F401

__all__ = [
    "APP_DIR",
    "APP_NAME",
    "CONFIG_PATH",
    "DEFAULT_DELETED_DIRNAME",
    "LOG_PATH",
    "MODE_IGNORE",
    "MODE_NORMAL",
    "MODE_NO_RECYCLE",
    "MODE_PERIODIC",
    "MODE_PERIODIC_NO_RECYCLE",
    "RULE_MODES",
    "VERSION",
    "LOGGER",
    "AppConfig",
    "BackupEngine",
    "FailuresDialog",
    "Job",
    "JobManager",
    "JobWizard",
    "Rule",
    "SmartBackupApp",
    "classify_error",
    "load_config",
    "save_config",
    "setup_logging",
    "config",
    "constants",
    "engine",
    "manager",
    "updates",
]


def main():
    setup_logging()
    if not HAVE_WATCHDOG:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            APP_NAME,
            "Λείπει η βιβλιοθήκη 'watchdog'.\n\nΤρέξε στο τερματικό:\npy -m pip install watchdog",
        )
        root.destroy()
        return 1
    app = SmartBackupApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
