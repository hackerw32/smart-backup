"""Κύριο παράθυρο της εφαρμογής."""

import os
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText

from ..constants import APP_NAME, RULE_MODES
from ..config import load_config, save_config
from ..i18n import Translator
from ..manager import JobManager
from .taskview import TaskTree
from .settings import SettingsDialog
from .wizard import JobWizard
from .failures import FailuresDialog

MODE_KEYS = {mode: key for key, mode in RULE_MODES}


class SmartBackupApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.i18n = Translator(self.cfg.language)
        self.messages = queue.Queue()
        self.progress_cache = {}
        self.job_status = {}
        self.failures = {}
        self._build_ui()
        self.manager = JobManager(self)
        self._load_jobs_to_tree()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(150, self._drain_messages)
        if self.cfg.autostart_watch:
            self.after(500, self._autostart)
        if not self.cfg.jobs:
            self.after(300, self._new_job_wizard)

    def _t(self, key, **kwargs):
        return self.i18n.t(key, **kwargs)

    def _build_ui(self):
        t = self.i18n.t
        self.title(t("app.title"))
        self.geometry("1080x780")
        self.minsize(940, 660)
        try:
            ttk.Style(self).theme_use("vista")
        except tk.TclError:
            pass

        self.select_all_var = tk.BooleanVar(value=False)
        self.detail_name = tk.StringVar(value="-")
        self.detail_source = tk.StringVar(value="-")
        self.detail_backup = tk.StringVar(value="-")
        self.detail_deleted = tk.StringVar(value="-")
        self.detail_rules = tk.StringVar(value="-")
        self.detail_schedule = tk.StringVar(value="-")
        self.current_file_var = tk.StringVar(value="")
        self.counts_var = tk.StringVar(value="")
        self.global_status = tk.StringVar(value=t("status.ready"))
        self.failure_button_text = tk.StringVar(value=self._failure_button_default())

        toolbar = ttk.Frame(self, padding=(10, 8, 10, 4))
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text=t("btn.new_task"), command=self._new_job_wizard).pack(side="left")
        ttk.Button(toolbar, text=t("btn.settings"), command=self._open_settings).pack(
            side="left", padx=4
        )

        paned = ttk.Panedwindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=10, pady=6)

        left = ttk.Frame(paned)
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)
        self.tasktree = TaskTree(
            left,
            on_select=self._on_select,
            on_activate=self._edit_task,
            on_context=self._show_context,
            on_check_change=self._on_check_change,
        )
        self.tasktree.grid(row=0, column=0, sticky="nsew")
        ttk.Checkbutton(
            left, text=t("chk.select_all"), variable=self.select_all_var,
            command=self._toggle_select_all,
        ).grid(row=1, column=0, sticky="w", pady=(6, 0))
        left_buttons = ttk.Frame(left)
        left_buttons.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        ttk.Button(left_buttons, text=t("btn.start"), command=self._start_targets).pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(left_buttons, text=t("btn.stop"), command=self._stop_targets).pack(
            side="left", fill="x", expand=True, padx=4
        )
        ttk.Button(left_buttons, text=t("btn.sync"), command=self._sync_targets).pack(
            side="left", fill="x", expand=True
        )

        right = ttk.Frame(paned)
        right.rowconfigure(3, weight=1)
        right.columnconfigure(0, weight=1)
        details = ttk.LabelFrame(right, text=t("lbl.task_details"), padding=8)
        details.grid(row=0, column=0, sticky="ew")
        details.columnconfigure(1, weight=1)
        for row, (label, var) in enumerate(
            [
                (t("lbl.name"), self.detail_name),
                (t("lbl.source"), self.detail_source),
                (t("lbl.backup"), self.detail_backup),
                (t("lbl.trash"), self.detail_deleted),
                (t("lbl.rules"), self.detail_rules),
                (t("lbl.schedule"), self.detail_schedule),
            ]
        ):
            ttk.Label(details, text=f"{label}:", width=12).grid(row=row, column=0, sticky="w")
            ttk.Label(details, textvariable=var, wraplength=500, justify="left").grid(
                row=row, column=1, sticky="w"
            )

        progress_frame = ttk.LabelFrame(right, text=t("lbl.progress"), padding=8)
        progress_frame.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        progress_frame.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(progress_frame, mode="determinate", maximum=100)
        self.progress.grid(row=0, column=0, sticky="ew")
        ttk.Label(progress_frame, textvariable=self.counts_var).grid(
            row=1, column=0, sticky="w", pady=(4, 0)
        )
        ttk.Label(progress_frame, textvariable=self.current_file_var, foreground="#333").grid(
            row=2, column=0, sticky="w"
        )

        actions = ttk.Frame(right)
        actions.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(actions, text=t("btn.open_backup"), command=self._open_backup).pack(side="left")
        ttk.Button(actions, text=t("btn.open_trash"), command=self._open_deleted).pack(
            side="left", padx=6
        )
        ttk.Button(
            actions, textvariable=self.failure_button_text, command=self._open_failures
        ).pack(side="right")

        log_frame = ttk.LabelFrame(right, text=t("lbl.messages"), padding=6)
        log_frame.grid(row=3, column=0, sticky="nsew", pady=(8, 0))
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        self.log_box = ScrolledText(log_frame, height=10, state="disabled", wrap="word")
        self.log_box.grid(row=0, column=0, sticky="nsew")
        ttk.Button(log_frame, text=t("btn.clear"), command=self._clear_log).grid(
            row=1, column=0, sticky="e", pady=(4, 0)
        )

        ttk.Label(self, textvariable=self.global_status, anchor="w", padding=(10, 4)).pack(
            fill="x"
        )

        paned.add(left, weight=0)
        paned.add(right, weight=1)

    def _rebuild_ui(self):
        checked = set(self.tasktree.checked)
        self.job_status = {}
        for child in self.winfo_children():
            child.destroy()
        self._build_ui()
        self.tasktree.checked = checked
        self._load_jobs_to_tree()

    def _load_jobs_to_tree(self):
        self.tasktree.clear()
        self.tasktree.set_headings(self._t("col.task"), self._t("col.status"))
        for job in self.cfg.jobs:
            if self.manager.is_running(job):
                status = (
                    self._t("state.watching")
                    if job.realtime
                    else self._t("state.active_no_realtime")
                )
                tag = "running"
            else:
                status = self.job_status.get(job.id) or self._t("state.idle")
                tag = "stopped"
            self.tasktree.insert_task(
                job.id, job.name, status, checked=job.id in self.tasktree.checked, tag=tag
            )
        children = self.tasktree.tree.get_children()
        if children:
            self.tasktree.tree.selection_set(children[0])
            self._on_select()
        self._on_check_change()

    def _job_by_id(self, job_id):
        return next((job for job in self.cfg.jobs if job.id == job_id), None)

    def _current_job(self):
        ids = self.tasktree.selected_ids()
        if ids:
            return self._job_by_id(ids[0])
        return None

    def _targets(self):
        ids = self.tasktree.checked_ids()
        if not ids:
            ids = self.tasktree.selected_ids()
        return [job for job in self.cfg.jobs if job.id in ids]

    def _mode_label(self, mode):
        return self._t(MODE_KEYS.get(mode, "")) or mode

    def _schedule_text(self, job):
        parts = [self._t("sched.realtime") if job.realtime else self._t("sched.no_realtime")]
        if job.periodic_minutes > 0:
            if job.periodic_minutes % 60 == 0:
                parts.append(self._t("sched.every_hours", n=job.periodic_minutes // 60))
            else:
                parts.append(self._t("sched.every_minutes", n=job.periodic_minutes))
        if job.sync_on_start:
            parts.append(self._t("sched.on_start"))
        return " | ".join(parts)

    def _on_select(self):
        job = self._current_job()
        if not job:
            return
        self.detail_name.set(job.name)
        self.detail_source.set(job.source or self._t("lbl.dash"))
        self.detail_backup.set(job.backup or self._t("lbl.dash"))
        self.detail_deleted.set(self.manager.engine(job).deleted_root() or self._t("lbl.dash"))
        if job.rules:
            self.detail_rules.set(
                "\n".join(f"{rule.path} -> {self._mode_label(rule.mode)}" for rule in job.rules)
            )
        else:
            self.detail_rules.set(self._t("lbl.none"))
        self.detail_schedule.set(self._schedule_text(job))
        data = self.progress_cache.get(job.id)
        if data:
            self._render_progress(data)
        else:
            self._set_bar("determinate", 0)
            self.counts_var.set("")
            self.current_file_var.set("")
        self._update_failure_button()

    def _toggle_select_all(self):
        self.tasktree.set_all_checked(bool(self.select_all_var.get()))

    def _on_check_change(self):
        children = self.tasktree.tree.get_children()
        all_checked = bool(children) and all(i in self.tasktree.checked for i in children)
        self.select_all_var.set(all_checked)

    def _new_job_wizard(self):
        JobWizard(self, self._on_wizard_save, i18n=self.i18n)

    def _open_settings(self):
        SettingsDialog(
            self, self.i18n, self.cfg.autostart_watch, self._apply_settings
        )

    def _apply_settings(self, language, autostart):
        self.cfg.language = language
        self.cfg.autostart_watch = autostart
        save_config(self.cfg)
        self.i18n.set_language(language)
        self._rebuild_ui()

    def _edit_task(self, job_id):
        job = self._job_by_id(job_id)
        if not job:
            return
        if self.manager.is_running(job):
            self.manager.stop(job)
            self.tasktree.set_status(job.id, self._t("state.idle"), "stopped")
        JobWizard(self, self._on_wizard_save, job=job, i18n=self.i18n)

    def _edit_current(self):
        job = self._current_job()
        if job:
            self._edit_task(job.id)

    def _on_wizard_save(self, job, start_now):
        if job not in self.cfg.jobs:
            self.cfg.jobs.append(job)
        save_config(self.cfg)
        self._load_jobs_to_tree()
        self.tasktree.tree.selection_set(job.id)
        self._on_select()
        if start_now:
            self.tasktree._set_check(job.id, True)
            self._on_check_change()
            self._start_targets()

    def _start_targets(self):
        targets = self._targets()
        if not targets:
            messagebox.showinfo(APP_NAME, self._t("msg.select_targets"))
            return
        errors = []
        started = 0
        for job in targets:
            self.failures.pop(job.id, None)
            self.manager.engine(job).reset_failures()
            try:
                self.manager.start(job)
            except Exception as exc:
                self.tasktree.set_status(job.id, self._t("state.error"), "error")
                errors.append((job, str(exc)))
                continue
            status = (
                self._t("state.watching")
                if job.realtime
                else self._t("state.active_no_realtime")
            )
            self.tasktree.set_status(job.id, status, "running")
            started += 1
        self._update_failure_button()
        if errors:
            text = "\n".join(f"- {job.name}: {msg}" for job, msg in errors)
            messagebox.showerror(APP_NAME, self._t("msg.some_start_failed", text=text))
        self.global_status.set(self._t("status.active_count", n=started))

    def _stop_targets(self):
        targets = self._targets()
        if not targets:
            messagebox.showinfo(APP_NAME, self._t("msg.select_targets"))
            return
        for job in targets:
            self.manager.stop(job)
            self.tasktree.set_status(job.id, self._t("state.idle"), "stopped")
        self._set_bar("determinate", 0)
        self.current_file_var.set("")
        self.counts_var.set("")
        self.global_status.set(self._t("status.ready"))

    def _sync_targets(self):
        targets = self._targets()
        if not targets:
            messagebox.showinfo(APP_NAME, self._t("msg.select_targets"))
            return
        for job in targets:
            threading.Thread(target=self._run_sync, args=(job,), daemon=True).start()

    def _run_sync(self, job):
        try:
            self.manager.engine(job).full_reconcile()
        except Exception as exc:
            self.messages.put(("log", job, f"Sync error: {exc}", "error"))

    def _delete_targets(self):
        targets = self._targets()
        if not targets:
            messagebox.showinfo(APP_NAME, self._t("msg.select_targets"))
            return
        if len(targets) == 1:
            question = self._t("msg.delete_one", name=targets[0].name)
        else:
            question = self._t("msg.delete_many", n=len(targets))
        if not messagebox.askyesno(APP_NAME, question):
            return
        for job in targets:
            self.manager.forget(job.id)
            self.progress_cache.pop(job.id, None)
            self.failures.pop(job.id, None)
            self.tasktree.checked.discard(job.id)
        self.cfg.jobs = [job for job in self.cfg.jobs if job not in targets]
        save_config(self.cfg)
        self._load_jobs_to_tree()
        self._update_failure_button()

    def _show_context(self, event):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label=self._t("btn.start"), command=self._start_targets)
        menu.add_command(label=self._t("btn.stop"), command=self._stop_targets)
        menu.add_command(label=self._t("btn.sync"), command=self._sync_targets)
        menu.add_separator()
        menu.add_command(label=self._t("menu.edit"), command=self._edit_current)
        menu.add_command(label=self._t("menu.delete"), command=self._delete_targets)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _autostart(self):
        started = 0
        for job in self.cfg.jobs:
            if self.manager.is_running(job):
                continue
            try:
                self.manager.start(job)
                status = (
                    self._t("state.watching")
                    if job.realtime
                    else self._t("state.active_no_realtime")
                )
                self.tasktree.set_status(job.id, status, "running")
                started += 1
            except Exception:
                self.tasktree.set_status(job.id, self._t("state.error"), "error")
        if started:
            self.global_status.set(self._t("status.active_count", n=started))

    def _open_backup(self):
        job = self._current_job()
        self._open_folder(job.backup if job else "")

    def _open_deleted(self):
        job = self._current_job()
        if not job:
            return
        self._open_folder(self.manager.engine(job).deleted_root())

    def _open_folder(self, path):
        if not path:
            messagebox.showinfo(APP_NAME, self._t("msg.no_folder"))
            return
        if not os.path.isdir(path):
            messagebox.showinfo(APP_NAME, self._t("msg.folder_missing", path=path))
            return
        try:
            os.startfile(path)
        except OSError as exc:
            messagebox.showerror(APP_NAME, self._t("msg.open_failed", error=exc))

    def on_engine_log(self, job, text, level):
        self.messages.put(("log", job, text, level))

    def on_engine_progress(self, job, data):
        self.messages.put(("progress", job, data))

    def on_engine_status(self, job, text):
        self.messages.put(("status", job, text))

    def on_engine_failure(self, job, reason, path, detail):
        self.messages.put(("failure", job, reason, path, detail))

    def _drain_messages(self):
        while True:
            try:
                message = self.messages.get_nowait()
            except queue.Empty:
                break
            kind = message[0]
            if kind == "log":
                _, job, text, level = message
                stamp = time.strftime("%H:%M:%S")
                prefix = f"[{job.name}] " if job else ""
                self.log_box.configure(state="normal")
                self.log_box.insert("end", f"[{stamp}] {prefix}{text}\n")
                if level in ("error", "warning"):
                    self.log_box.see("end")
                self.log_box.configure(state="disabled")
            elif kind == "progress":
                _, job, data = message
                self.progress_cache[job.id] = data
                selected = self._current_job()
                if selected and selected.id == job.id:
                    self._render_progress(data)
                self._apply_progress_to_row(job, data)
            elif kind == "status":
                _, job, text = message
                tag = "running" if text != self._t("state.idle") else "stopped"
                self.tasktree.set_status(job.id, text, tag)
            elif kind == "failure":
                _, job, reason, path, detail = message
                bucket = self.failures.setdefault(job.id, {})
                entry = bucket.setdefault(reason, {"count": 0, "detail": detail, "items": []})
                entry["count"] += 1
                entry["detail"] = detail
                entry["items"].append((path, detail))
                self._update_failure_button()
        self.after(150, self._drain_messages)

    def _failure_button_default(self):
        return self._t("fail.button_all", n=0)

    def _total_failures(self, job=None):
        if job is not None:
            return sum(e["count"] for e in self.failures.get(job.id, {}).values())
        return sum(
            entry["count"] for bucket in self.failures.values() for entry in bucket.values()
        )

    def _update_failure_button(self):
        job = self._current_job()
        if job is not None:
            self.failure_button_text.set(
                self._t("fail.button", name=job.name, n=self._total_failures(job))
            )
        else:
            self.failure_button_text.set(
                self._t("fail.button_all", n=self._total_failures())
            )

    def _open_failures(self):
        job = self._current_job()
        if job is not None:
            failures = self.failures.setdefault(job.id, {})
            title = self._t("fail.title_named", name=job.name)
        else:
            merged = {}
            for bucket in self.failures.values():
                for reason, entry in bucket.items():
                    target = merged.setdefault(
                        reason, {"count": 0, "detail": "", "items": []}
                    )
                    target["count"] += entry["count"]
                    target["detail"] = entry["detail"]
                    target["items"].extend(entry["items"])
            failures = merged
            title = self._t("fail.title_all")
        if not failures:
            messagebox.showinfo(APP_NAME, self._t("msg.no_failures"))
            return
        dialog = FailuresDialog(self, title, failures, i18n=self.i18n)
        self.wait_window(dialog)
        self._update_failure_button()

    def _apply_progress_to_row(self, job, data):
        phase = data.get("phase")
        text = None
        if phase == "scan":
            text = self._t("prog.scan_folder", folder=self._folder_label(data.get("current")))
        elif phase == "copy":
            total = data.get("total") or 0
            done = data.get("done") or 0
            if total:
                text = self._t("prog.copy", percent=int(done * 100 / total))
            else:
                text = self._t(
                    "prog.copy_file", name=os.path.basename(data.get("current") or "")
                )
        elif phase == "delete":
            text = self._t("prog.delete_folder", folder=self._folder_label(data.get("current")))
        if not text or self.tasktree.get_status(job.id) == text:
            return
        self.tasktree.set_status(job.id, text, "running")

    def _folder_label(self, value):
        if not value or value == ".":
            return self._t("prog.root")
        return os.path.basename(value.rstrip("\\/"))

    def _render_progress(self, data):
        phase = data.get("phase")
        total = data.get("total") or 0
        done = data.get("done") or 0
        current = data.get("current") or ""
        if phase == "copy" and total:
            self._set_bar("determinate", min(100, int(done * 100 / total)))
            self.counts_var.set(self._t("prog.files_progress", done=done, total=total))
        elif phase == "copy":
            self._set_bar("determinate", 0)
            self.counts_var.set(self._t("prog.watching_changes"))
        elif phase == "scan":
            self._set_bar("indeterminate", 0)
            self.counts_var.set(self._t("prog.files_found", n=done))
            self.current_file_var.set(
                self._t("prog.scan_folder", folder=self._pretty_dir(current))
            )
        elif phase == "delete":
            self._set_bar("indeterminate", 0)
            self.counts_var.set(self._t("prog.delete_check", n=done))
            self.current_file_var.set(
                self._t("prog.delete_folder", folder=self._pretty_dir(current))
            )
        else:
            self._set_bar("determinate", 100 if phase == "idle" and total else 0)
            self.counts_var.set(self._t("prog.done") if phase == "idle" and total else "")
        if phase not in ("scan", "delete") and current:
            self.current_file_var.set(self._t("prog.current", name=current))
        elif phase == "idle":
            self.current_file_var.set("")

    def _pretty_dir(self, value):
        if not value or value == ".":
            return self._t("prog.root_folder")
        return os.path.basename(value.rstrip("\\/")) + f"  [{value}]"

    def _set_bar(self, mode, value):
        if str(self.progress.cget("mode")) != mode:
            if mode == "indeterminate":
                self.progress.stop()
                self.progress.configure(mode="indeterminate")
                self.progress.start(12)
            else:
                self.progress.stop()
                self.progress.configure(mode="determinate")
        if mode == "determinate":
            self.progress["value"] = value

    def _clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def _on_close(self):
        running = [job for job in self.cfg.jobs if self.manager.is_running(job)]
        if running and not messagebox.askyesno(
            APP_NAME, self._t("msg.close_confirm", n=len(running))
        ):
            return
        save_config(self.cfg)
        self.manager.stop_all_engines()
        self.destroy()
