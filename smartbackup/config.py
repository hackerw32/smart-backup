"""Μοντέλο δεδομένων (Job/Rule) και αποθήκευση/φόρτωση ρυθμίσεων."""

import os
import json
import uuid
import shutil
from dataclasses import dataclass, field, asdict

from .constants import (
    APP_DIR,
    CONFIG_PATH,
    MODE_IGNORE,
    MODE_NO_RECYCLE,
    MODE_PERIODIC,
    MODE_PERIODIC_NO_RECYCLE,
)
from .i18n import DEFAULT_LANGUAGE, LANGUAGES
from .logging_setup import LOGGER


@dataclass
class Rule:
    path: str = ""
    mode: str = MODE_IGNORE


@dataclass
class Job:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = "Νέα εργασία"
    source: str = ""
    backup: str = ""
    deleted_store: str = ""
    deleted_layout: str = "preserve"
    realtime: bool = True
    periodic_minutes: int = 0
    sync_on_start: bool = True
    rules: list = field(default_factory=list)


@dataclass
class AppConfig:
    jobs: list = field(default_factory=list)
    autostart_watch: bool = False
    language: str = DEFAULT_LANGUAGE


def _clean_rules(raw):
    rules = []
    if isinstance(raw, list):
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            path = str(entry.get("path", "")).strip()
            mode = entry.get("mode", MODE_IGNORE)
            if not path:
                continue
            if mode not in (
                MODE_IGNORE,
                MODE_NO_RECYCLE,
                MODE_PERIODIC,
                MODE_PERIODIC_NO_RECYCLE,
            ):
                mode = MODE_IGNORE
            rules.append(Rule(path=path, mode=mode))
    return rules


def _clean_job(data):
    job = Job()
    if isinstance(data.get("id"), str) and data["id"]:
        job.id = data["id"]
    if isinstance(data.get("name"), str) and data["name"].strip():
        job.name = data["name"].strip()
    for key in ("source", "backup", "deleted_store"):
        if isinstance(data.get(key), str):
            setattr(job, key, data[key])
    if data.get("deleted_layout") in ("preserve", "flat"):
        job.deleted_layout = data["deleted_layout"]
    job.realtime = bool(data.get("realtime", True))
    job.sync_on_start = bool(data.get("sync_on_start", True))
    try:
        job.periodic_minutes = max(0, int(data.get("periodic_minutes", 0)))
    except (TypeError, ValueError):
        job.periodic_minutes = 0
    if isinstance(data.get("rules"), list):
        job.rules = _clean_rules(data["rules"])
    elif isinstance(data.get("exclusions"), list):
        job.rules = [
            Rule(path=str(x), mode=MODE_IGNORE) for x in data["exclusions"] if x
        ]
    return job


def _migrate_legacy_config():
    legacy = os.path.join(APP_DIR, "config.json")
    if os.path.normcase(legacy) == os.path.normcase(CONFIG_PATH):
        return
    if os.path.exists(CONFIG_PATH) or not os.path.exists(legacy):
        return
    try:
        shutil.copy2(legacy, CONFIG_PATH)
        LOGGER.info("Migrated config to %s", CONFIG_PATH)
    except OSError as exc:
        LOGGER.warning("Config migration failed: %s", exc)


def load_config():
    _migrate_legacy_config()
    cfg = AppConfig()
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError, TypeError):
        return cfg
    if not isinstance(data, dict):
        return cfg
    cfg.autostart_watch = bool(data.get("autostart_watch", False))
    if data.get("language") in [code for _, code in LANGUAGES]:
        cfg.language = data["language"]
    jobs = data.get("jobs")
    if isinstance(jobs, list) and jobs:
        for entry in jobs:
            if isinstance(entry, dict):
                cfg.jobs.append(_clean_job(entry))
        return cfg
    if data.get("source") or data.get("backup"):
        legacy = _clean_job(data)
        legacy.name = os.path.basename(legacy.source.rstrip("\\/")) or "Backup"
        cfg.jobs.append(legacy)
    return cfg


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "autostart_watch": cfg.autostart_watch,
                    "language": cfg.language,
                    "jobs": [asdict(job) for job in cfg.jobs],
                },
                fh,
                ensure_ascii=False,
                indent=2,
            )
        return True
    except OSError as exc:
        LOGGER.error("Αποτυχία αποθήκευσης ρυθμίσεων: %s", exc)
        return False
