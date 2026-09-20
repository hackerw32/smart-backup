"""Ο πυρήνας συγχρονισμού: watcher, αντιγραφές, καλάθι διαγραφών, αποτυχίες."""

import os
import time
import shutil
import hashlib
import threading
import traceback
import logging

from .constants import (
    APP_DIR,
    FILE_ATTRIBUTE_REPARSE_POINT,
    TEMP_SUFFIX,
    DEFAULT_DELETED_DIRNAME,
    SAME_NAME_SUFFIX,
    SKIP_NAMES,
    SKIP_SUFFIXES,
    MODE_IGNORE,
    MODE_NO_RECYCLE,
    MODE_PERIODIC,
    MODE_PERIODIC_NO_RECYCLE,
)
from .i18n import Translator
from .logging_setup import LOGGER

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler

    HAVE_WATCHDOG = True
except ImportError:
    Observer = None
    FileSystemEventHandler = object
    HAVE_WATCHDOG = False


def classify_error(exc):
    """Επιστρέφει κλειδί μετάφρασης για την κατηγορία του σφάλματος."""
    winerror = getattr(exc, "winerror", None)
    errno = getattr(exc, "errno", None)
    if winerror == 32:
        return "err.in_use"
    if winerror == 5 or errno == 13 or isinstance(exc, PermissionError):
        return "err.access"
    if winerror == 3 or isinstance(exc, FileNotFoundError):
        return "err.not_found"
    if winerror == 112 or errno == 28:
        return "err.disk_full"
    if isinstance(exc, OSError):
        return "err.system"
    return "err.unknown"


class _Handler(FileSystemEventHandler):
    def __init__(self, submit, submit_move):
        super().__init__()
        self.submit = submit
        self.submit_move = submit_move

    def on_any_event(self, event):
        try:
            if event.is_directory and event.event_type == "modified":
                return
            if event.event_type == "moved":
                self.submit_move(event.src_path, event.dest_path)
            else:
                self.submit(event.src_path)
        except Exception:
            LOGGER.error("Σφάλμα χειριστή συμβάντων:\n%s", traceback.format_exc())


class BackupEngine:
    def __init__(
        self, job, on_log, on_progress, on_status, on_failure, logger=None, translator=None
    ):
        self.job = job
        self.on_log = on_log
        self.on_progress = on_progress
        self.on_status = on_status
        self.on_failure = on_failure
        self.logger = logger or LOGGER
        self.t = (translator or Translator()).t
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.active = False
        self.worker = None
        self.observer = None
        self.periodic_thread = None
        self._pending = {}
        self._moves = []
        self._cv = threading.Condition()
        self.failure_counts = {}
        self.failure_total = 0

    def source(self):
        return os.path.abspath(self.job.source) if self.job.source else ""

    def backup(self):
        return os.path.abspath(self.job.backup) if self.job.backup else ""

    def deleted_root(self):
        if self.job.deleted_store.strip():
            return os.path.abspath(self.job.deleted_store.strip())
        if not self.backup():
            return ""
        return os.path.join(self.backup(), DEFAULT_DELETED_DIRNAME)

    def log(self, message, level="info"):
        try:
            self.logger.log(getattr(logging, level.upper(), logging.INFO), message)
        except Exception:
            pass
        try:
            self.on_log(self.job, message, level)
        except Exception:
            pass

    def _progress(self, **data):
        try:
            self.on_progress(self.job, data)
        except Exception:
            pass

    def _status(self, text):
        try:
            self.on_status(self.job, text)
        except Exception:
            pass

    def _record_failure(self, reason, path, detail):
        self.failure_counts[reason] = self.failure_counts.get(reason, 0) + 1
        self.failure_total += 1
        try:
            self.on_failure(self.job, reason, path, detail)
        except Exception:
            pass

    def reset_failures(self):
        self.failure_counts = {}
        self.failure_total = 0

    @staticmethod
    def _norm(path):
        return os.path.normcase(os.path.abspath(path))

    @staticmethod
    def _within(child, parent):
        child = os.path.normcase(os.path.abspath(child))
        parent = os.path.normcase(os.path.abspath(parent))
        if child == parent:
            return True
        parent = parent.rstrip("\\/") + os.sep
        return child.startswith(parent)

    def _rule_mode(self, path):
        if not path:
            return None
        target = self._norm(path)
        source = self.source()
        best_mode = None
        best_len = -1
        for rule in self.job.rules:
            if not rule.path:
                continue
            root = rule.path if os.path.isabs(rule.path) else os.path.join(source, rule.path)
            root_norm = self._norm(root)
            if target == root_norm or (target + os.sep).startswith(
                root_norm.rstrip("\\/") + os.sep
            ):
                if len(root_norm) > best_len:
                    best_len = len(root_norm)
                    best_mode = rule.mode
        return best_mode

    def matching_mode(self, path):
        if not path:
            return None
        target = self._norm(path)
        for special in (self.backup(), self.deleted_root(), APP_DIR):
            if special and (
                target == self._norm(special)
                or (target + os.sep).startswith(self._norm(special).rstrip("\\/") + os.sep)
            ):
                return MODE_IGNORE
        return self._rule_mode(path)

    def _user_ignored(self, path):
        return self._rule_mode(path) == MODE_IGNORE

    def is_excluded(self, path):
        return self.matching_mode(path) == MODE_IGNORE

    def _is_periodic(self, path):
        return self.matching_mode(path) in (MODE_PERIODIC, MODE_PERIODIC_NO_RECYCLE)

    def _is_no_recycle(self, path):
        return self.matching_mode(path) in (MODE_NO_RECYCLE, MODE_PERIODIC_NO_RECYCLE)

    def _in_deleted_root(self, path):
        deleted = self.deleted_root()
        if not deleted:
            return False
        return self._within(path, deleted)

    @staticmethod
    def _is_reparse(path):
        try:
            info = os.lstat(path)
        except OSError:
            return False
        return bool(getattr(info, "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT)

    @staticmethod
    def _skip_name(name):
        low = name.lower()
        if low in SKIP_NAMES:
            return True
        return low.endswith(SKIP_SUFFIXES)

    def _rel(self, path):
        try:
            rel = os.path.relpath(os.path.abspath(path), self.source())
        except ValueError:
            return None
        if rel == "." or rel == ".." or rel.startswith(".." + os.sep):
            return None
        return rel

    @staticmethod
    def _sha256(path):
        digest = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @classmethod
    def _files_identical(cls, first, second):
        try:
            if os.path.getsize(first) != os.path.getsize(second):
                return False
            return cls._sha256(first) == cls._sha256(second)
        except OSError:
            return False

    @staticmethod
    def _unique_path(dest):
        if not os.path.exists(dest):
            return dest
        base, ext = os.path.splitext(dest)
        counter = 1
        while True:
            candidate = f"{base}_{SAME_NAME_SUFFIX}{counter}{ext}"
            if not os.path.exists(candidate):
                return candidate
            counter += 1

    @staticmethod
    def _needs_copy(src, dst):
        try:
            if not os.path.isfile(dst):
                return True
            src_info = os.stat(src)
            dst_info = os.stat(dst)
            return (
                src_info.st_size != dst_info.st_size
                or int(src_info.st_mtime) != int(dst_info.st_mtime)
            )
        except OSError:
            return True

    def _copy_file(self, src, dst):
        if self._skip_name(os.path.basename(src)):
            return False
        if not self._needs_copy(src, dst):
            return False
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
        except OSError as exc:
            reason = classify_error(exc)
            self._record_failure(reason, os.path.dirname(dst), str(exc))
            self.log(
                self.t("log.mkdir_failed", reason=self.t(reason), path=os.path.dirname(dst)),
                "error",
            )
            return False
        tmp = dst + TEMP_SUFFIX
        last_error = None
        for attempt in range(4):
            try:
                shutil.copy2(src, tmp)
                os.replace(tmp, dst)
                return True
            except (PermissionError, OSError) as exc:
                last_error = exc
                try:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                except OSError:
                    pass
                time.sleep(0.25 * (attempt + 1))
        reason = classify_error(last_error)
        self._record_failure(reason, src, str(last_error))
        self.log(self.t("log.copy_failed", reason=self.t(reason), src=src), "warning")
        return False

    def _purge(self, path, rel, is_dir, key="log.purged"):
        try:
            if is_dir:
                shutil.rmtree(path, ignore_errors=False)
            else:
                os.remove(path)
            self.log(self.t(key, rel=rel))
        except OSError as exc:
            reason = classify_error(exc)
            self._record_failure(reason, path, str(exc))
            self.log(
                self.t("log.purge_failed", reason=self.t(reason), rel=rel), "error"
            )

    def _move_to_deleted(self, mirror_path, rel, is_dir):
        deleted_root = self.deleted_root()
        if not deleted_root or self._in_deleted_root(mirror_path):
            return
        source_path = os.path.join(self.source(), rel)
        if self._is_no_recycle(source_path):
            self._purge(mirror_path, rel, is_dir)
            return
        if self.job.deleted_layout == "flat":
            dest = os.path.join(deleted_root, os.path.basename(mirror_path.rstrip("\\/")))
        else:
            dest = os.path.join(deleted_root, rel)
        try:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
        except OSError as exc:
            reason = classify_error(exc)
            self._record_failure(reason, os.path.dirname(dest), str(exc))
            self.log(
                self.t("log.trash_dir_failed", reason=self.t(reason), dest=dest), "error"
            )
            return
        if not is_dir and os.path.isfile(dest) and self._files_identical(dest, mirror_path):
            try:
                os.remove(mirror_path)
                self.log(self.t("log.identical_removed", rel=rel))
                return
            except OSError:
                pass
        final = self._unique_path(dest)
        last_error = None
        for attempt in range(4):
            try:
                shutil.move(mirror_path, final)
                if self.job.deleted_layout == "flat":
                    shown = os.path.basename(final)
                else:
                    shown = os.path.relpath(final, deleted_root)
                self.log(self.t("log.moved_to_trash", rel=rel, shown=shown))
                return
            except (PermissionError, OSError) as exc:
                last_error = exc
                time.sleep(0.25 * (attempt + 1))
        reason = classify_error(last_error)
        self._record_failure(reason, mirror_path, str(last_error))
        self.log(
            self.t("log.trash_failed", reason=self.t(reason), path=mirror_path), "error"
        )

    def _sync_path(self, path):
        abspath = os.path.abspath(path)
        if self.is_excluded(abspath) or self._is_reparse(abspath):
            return
        if self._is_periodic(abspath):
            return
        rel = self._rel(abspath)
        if rel is None:
            return
        mirror = os.path.join(self.backup(), rel)
        if os.path.isdir(abspath):
            try:
                os.makedirs(mirror, exist_ok=True)
            except OSError as exc:
                reason = classify_error(exc)
                self._record_failure(reason, mirror, str(exc))
                self.log(
                    self.t("log.mkdir_failed", reason=self.t(reason), path=mirror), "error"
                )
            return
        if os.path.isfile(abspath):
            self._progress(phase="copy", current=rel, done=0, total=0, realtime=True)
            self._copy_file(abspath, mirror)
            return
        if os.path.isdir(mirror):
            self._move_to_deleted(mirror, rel, is_dir=True)
        elif os.path.isfile(mirror):
            self._move_to_deleted(mirror, rel, is_dir=False)

    def sync_path(self, path):
        with self.lock:
            try:
                self._sync_path(path)
            except Exception:
                self.log(
                    self.t("log.sync_error", tb=traceback.format_exc()), "error"
                )

    def sync_move(self, src, dest):
        with self.lock:
            try:
                self._sync_move(src, dest)
            except Exception:
                self.log(
                    self.t("log.rename_error", tb=traceback.format_exc()), "error"
                )

    def _sync_move(self, src, dest):
        src = os.path.abspath(src)
        dest = os.path.abspath(dest) if dest else None
        if self.is_excluded(src):
            if dest:
                self._sync_path(dest)
            return
        if self._is_periodic(src):
            return
        dest_inside = bool(
            dest and self._within(dest, self.source()) and not self.is_excluded(dest)
        )
        if dest_inside:
            rel_src = self._rel(src)
            rel_dest = self._rel(dest)
            if rel_src is not None and rel_dest is not None:
                mirror_src = os.path.join(self.backup(), rel_src)
                mirror_dest = os.path.join(self.backup(), rel_dest)
                if os.path.exists(mirror_src):
                    try:
                        os.makedirs(os.path.dirname(mirror_dest), exist_ok=True)
                        if os.path.isdir(mirror_src):
                            if os.path.isdir(mirror_dest):
                                shutil.rmtree(mirror_dest, ignore_errors=True)
                            shutil.move(mirror_src, mirror_dest)
                        else:
                            os.replace(mirror_src, mirror_dest)
                    except OSError as exc:
                        reason = classify_error(exc)
                        self._record_failure(reason, mirror_src, str(exc))
                        self.log(
                            self.t("log.rename_failed", reason=self.t(reason), rel=rel_src),
                            "warning",
                        )
                self._sync_path(dest)
            return
        self._sync_path(src)

    def _walk_error(self, exc):
        reason = classify_error(exc)
        self._record_failure(reason, getattr(exc, "filename", "") or "", str(exc))

    def full_reconcile(self):
        with self.lock:
            source = self.source()
            backup = self.backup()
            if not source or not os.path.isdir(source):
                self.log(self.t("log.invalid_source"), "error")
                return
            if not backup:
                self.log(self.t("log.no_backup"), "error")
                return
            before = dict(self.failure_counts)
            self._progress(phase="scan", current="", done=0, total=0)
            self.log(self.t("log.reconcile_start"))
            try:
                os.makedirs(backup, exist_ok=True)
            except OSError as exc:
                reason = classify_error(exc)
                self._record_failure(reason, backup, str(exc))
                self.log(
                    self.t("log.backup_create_failed", reason=self.t(reason), exc=exc),
                    "error",
                )
                return
            tasks = []
            last_scan_emit = 0.0
            try:
                for root, dirs, files in os.walk(source, topdown=True, onerror=self._walk_error):
                    if self.stop_event.is_set():
                        return
                    dirs[:] = [
                        d
                        for d in dirs
                        if not self.is_excluded(os.path.join(root, d))
                        and not self._is_reparse(os.path.join(root, d))
                    ]
                    if self.is_excluded(root):
                        continue
                    rel_dir = self._rel(root)
                    now = time.monotonic()
                    if now - last_scan_emit >= 0.08:
                        self._progress(
                            phase="scan", current=rel_dir or ".", done=len(tasks), total=0
                        )
                        last_scan_emit = now
                    if rel_dir:
                        try:
                            os.makedirs(os.path.join(backup, rel_dir), exist_ok=True)
                        except OSError as exc:
                            reason = classify_error(exc)
                            self._record_failure(reason, rel_dir, str(exc))
                            self.log(
                                self.t(
                                    "log.mkdir_rel_failed",
                                    rel=rel_dir,
                                    reason=self.t(reason),
                                ),
                                "error",
                            )
                    for name in files:
                        full = os.path.join(root, name)
                        if (
                            self.is_excluded(full)
                            or self._is_reparse(full)
                            or self._skip_name(name)
                        ):
                            continue
                        rel = self._rel(full)
                        if rel is not None:
                            tasks.append((full, rel))
            except Exception:
                self.log(self.t("log.scan_error", tb=traceback.format_exc()), "error")
            total = len(tasks)
            self._progress(phase="copy", current="", done=0, total=total)
            copied = 0
            for index, (full, rel) in enumerate(tasks, 1):
                if self.stop_event.is_set():
                    return
                self._progress(phase="copy", current=rel, done=index, total=total)
                if self._copy_file(full, os.path.join(backup, rel)):
                    copied += 1
            deleted = 0
            removed = 0
            try:
                self._progress(phase="delete", current="", done=0, total=0)
                last_del_emit = 0.0
                if os.path.isdir(backup):
                    for root, dirs, files in os.walk(
                        backup, topdown=False, onerror=self._walk_error
                    ):
                        if self.stop_event.is_set():
                            return
                        if self._in_deleted_root(root):
                            dirs[:] = []
                            continue
                        now = time.monotonic()
                        if now - last_del_emit >= 0.08:
                            self._progress(
                                phase="delete",
                                current=os.path.relpath(root, backup),
                                done=deleted,
                                total=0,
                            )
                            last_del_emit = now
                        for name in files:
                            mirror = os.path.join(root, name)
                            if self._is_reparse(mirror):
                                continue
                            rel = os.path.relpath(mirror, backup)
                            source_file = os.path.join(source, rel)
                            if self._user_ignored(source_file):
                                self._purge(
                                    mirror, rel, is_dir=False, key="log.removed_ignored"
                                )
                                removed += 1
                                continue
                            if self.is_excluded(source_file):
                                continue
                            if not os.path.exists(source_file):
                                self._move_to_deleted(mirror, rel, is_dir=False)
                                deleted += 1
                        for name in dirs:
                            mirror_dir = os.path.join(root, name)
                            if self._in_deleted_root(mirror_dir):
                                continue
                            rel = os.path.relpath(mirror_dir, backup)
                            source_dir = os.path.join(source, rel)
                            if self._user_ignored(source_dir):
                                try:
                                    if not os.listdir(mirror_dir):
                                        os.rmdir(mirror_dir)
                                except OSError:
                                    pass
                                continue
                            if self.is_excluded(source_dir):
                                continue
                            if not os.path.isdir(source_dir):
                                try:
                                    if not os.listdir(mirror_dir):
                                        os.rmdir(mirror_dir)
                                except OSError:
                                    pass
            except Exception:
                self.log(
                    self.t("log.delete_check_error", tb=traceback.format_exc()), "error"
                )
            if self.stop_event.is_set():
                return
            self._progress(phase="idle", current="", done=total, total=total)
            self.log(
                self.t(
                    "log.reconcile_done",
                    total=total,
                    copied=copied,
                    deleted=deleted,
                    removed=removed,
                )
            )
            new_counts = {
                reason: self.failure_counts[reason] - before.get(reason, 0)
                for reason in self.failure_counts
            }
            new_counts = {reason: n for reason, n in new_counts.items() if n > 0}
            if new_counts:
                parts = ", ".join(
                    f"{reason} ({n})"
                    for reason, n in sorted(new_counts.items(), key=lambda item: -item[1])
                )
                self.log(self.t("log.run_failures", parts=parts), "warning")

    def _submit(self, path):
        if not path:
            return
        with self._cv:
            self._pending[os.path.abspath(path)] = time.monotonic() + 0.5
            self._cv.notify_all()

    def _submit_move(self, src, dest):
        if not src:
            return
        with self._cv:
            self._moves.append((os.path.abspath(src), os.path.abspath(dest) if dest else None))
            self._cv.notify_all()

    def _worker_loop(self):
        while not self.stop_event.is_set():
            moves = []
            due = []
            with self._cv:
                if self._moves:
                    moves = self._moves
                    self._moves = []
                now = time.monotonic()
                due = [p for p, when in self._pending.items() if when <= now]
                for path in due:
                    self._pending.pop(path, None)
                if not moves and not due:
                    if not self._pending:
                        self._cv.wait(timeout=0.5)
                    else:
                        wait = min(self._pending.values()) - now
                        self._cv.wait(timeout=max(0.05, min(wait, 0.5)))
                    continue
            for src, dest in moves:
                if self.stop_event.is_set():
                    return
                self.sync_move(src, dest)
            for path in due:
                if self.stop_event.is_set():
                    return
                self.sync_path(path)

    def _periodic_loop(self):
        interval = max(1, self.job.periodic_minutes) * 60
        while not self.stop_event.wait(interval):
            if self.stop_event.is_set():
                return
            self.log(self.t("log.periodic", n=self.job.periodic_minutes))
            self.full_reconcile()

    def is_running(self):
        return self.active

    def start(self):
        if self.active:
            return
        source = self.source()
        backup = self.backup()
        if not source or not os.path.isdir(source):
            raise RuntimeError(self.t("err.source_missing"))
        if not backup:
            raise RuntimeError(self.t("err.backup_missing"))
        if os.path.normcase(source) == os.path.normcase(backup):
            raise RuntimeError(self.t("err.same_folder"))
        if self.job.realtime and not HAVE_WATCHDOG:
            raise RuntimeError(self.t("err.no_watchdog"))
        try:
            os.makedirs(backup, exist_ok=True)
        except OSError as exc:
            raise RuntimeError(self.t("err.backup_create", exc=exc)) from exc
        self.stop_event.clear()
        self.active = True
        if self.job.realtime:
            self.worker = threading.Thread(target=self._worker_loop, daemon=True)
            self.worker.start()
            self.observer = Observer()
            self.observer.schedule(
                _Handler(self._submit, self._submit_move), source, recursive=True
            )
            self.observer.start()
            self._status(self.t("state.watching"))
            self.log(self.t("log.start_realtime", source=source))
        else:
            self._status(self.t("state.active_no_realtime"))
            self.log(self.t("log.start_scheduled"))
        if self.job.sync_on_start:
            threading.Thread(target=self.full_reconcile, daemon=True).start()
        if self.job.periodic_minutes > 0:
            self.periodic_thread = threading.Thread(target=self._periodic_loop, daemon=True)
            self.periodic_thread.start()
            self.log(self.t("log.periodic_set", n=self.job.periodic_minutes))

    def stop(self):
        self.stop_event.set()
        with self._cv:
            self._cv.notify_all()
        if self.observer is not None:
            try:
                self.observer.stop()
                self.observer.join(timeout=5)
            except Exception:
                pass
            self.observer = None
        if self.worker is not None:
            self.worker.join(timeout=5)
            self.worker = None
        if self.periodic_thread is not None:
            self.periodic_thread.join(timeout=5)
            self.periodic_thread = None
        with self._cv:
            self._pending.clear()
            self._moves.clear()
        self.active = False
        self._progress(phase="idle", current="", done=0, total=0)
        self._status(self.t("state.idle"))
        self.log(self.t("log.stopped"))
