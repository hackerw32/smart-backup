"""Smart Backup - πακέτο εφαρμογής."""

from .constants import (
    APP_DIR,
    APP_NAME,
    CONFIG_PATH,
    LOG_PATH,
    DEFAULT_DELETED_DIRNAME,
    MODE_IGNORE,
    MODE_NORMAL,
    MODE_NO_RECYCLE,
    MODE_PERIODIC,
    MODE_PERIODIC_NO_RECYCLE,
    RULE_MODES,
    VERSION,
)
from .i18n import DEFAULT_LANGUAGE, LANGUAGES, Translator
from .logging_setup import LOGGER, setup_logging
from .config import AppConfig, Job, Rule, load_config, save_config
from .engine import HAVE_WATCHDOG, BackupEngine, classify_error
from .manager import JobManager
from .ui.app import SmartBackupApp
from .ui.failures import FailuresDialog
from .ui.wizard import JobWizard

from . import config, constants, engine, manager  # noqa: F401  (για tests/patching)

__all__ = [
    "APP_DIR",
    "APP_NAME",
    "CONFIG_PATH",
    "LOG_PATH",
    "DEFAULT_DELETED_DIRNAME",
    "MODE_IGNORE",
    "MODE_NORMAL",
    "MODE_NO_RECYCLE",
    "MODE_PERIODIC",
    "MODE_PERIODIC_NO_RECYCLE",
    "RULE_MODES",
    "VERSION",
    "DEFAULT_LANGUAGE",
    "LANGUAGES",
    "Translator",
    "LOGGER",
    "setup_logging",
    "AppConfig",
    "Job",
    "Rule",
    "load_config",
    "save_config",
    "HAVE_WATCHDOG",
    "BackupEngine",
    "classify_error",
    "JobManager",
    "SmartBackupApp",
    "FailuresDialog",
    "JobWizard",
]
