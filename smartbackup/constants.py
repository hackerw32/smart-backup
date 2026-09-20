"""Σταθερές και μονοπάτια της εφαρμογής."""

import os
import sys

APP_NAME = "Smart Backup"
VERSION = "1.0.1"
UPDATE_REPO = "hackerw32/smart-backup"
UPDATE_API = f"https://api.github.com/repos/{UPDATE_REPO}/releases/latest"
RELEASES_URL = f"https://github.com/{UPDATE_REPO}/releases/latest"

if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _data_dir():
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    target = os.path.join(base, "SmartBackup")
    try:
        os.makedirs(target, exist_ok=True)
        return target
    except OSError:
        return APP_DIR


DATA_DIR = _data_dir()
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
LOG_PATH = os.path.join(DATA_DIR, "smart_backup.log")

FILE_ATTRIBUTE_REPARSE_POINT = 0x400
TEMP_SUFFIX = ".sb_tmp"
DEFAULT_DELETED_DIRNAME = "_DeletedFiles"
SAME_NAME_SUFFIX = "dsn"

SKIP_NAMES = {"ntuser.dat", "ntuser.ini", "ntuser.dat.log1", "ntuser.dat.log2"}
SKIP_SUFFIXES = (".regtrans-ms", ".blf", ".log1", ".log2")

MODE_NORMAL = ""
MODE_IGNORE = "ignore"
MODE_NO_RECYCLE = "no_recycle"
MODE_PERIODIC = "periodic"
MODE_PERIODIC_NO_RECYCLE = "periodic_no_recycle"

RULE_MODES = [
    ("mode.normal", MODE_NORMAL),
    ("mode.ignore", MODE_IGNORE),
    ("mode.no_recycle", MODE_NO_RECYCLE),
    ("mode.periodic", MODE_PERIODIC),
    ("mode.periodic_no_recycle", MODE_PERIODIC_NO_RECYCLE),
]
