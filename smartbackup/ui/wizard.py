"""Οδηγός δημιουργίας/επεξεργασίας εργασίας (βήμα-βήμα)."""

import os
import uuid
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText

from ..constants import APP_NAME, DEFAULT_DELETED_DIRNAME, MODE_NORMAL, RULE_MODES
from ..config import Job, Rule
from ..engine import BackupEngine
from ..i18n import Translator


class JobWizard(tk.Toplevel):
    STEP_KEYS = [
        "wiz.step.source",
        "wiz.step.backup",
        "wiz.step.rules",
        "wiz.step.trash",
        "wiz.step.schedule",
        "wiz.step.summary",
    ]

    def __init__(self, master, on_save, job=None, i18n=None):
        super().__init__(master)
        self.i18n = i18n or Translator()
        t = self.i18n.t
        self.on_save = on_save
        self.result_job = job
        self.data = {
            "id": job.id if job else uuid.uuid4().hex[:12],
            "name": job.name if job else "",
            "source": job.source if job else "",
            "backup": job.backup if job else "",
            "deleted_store": job.deleted_store if job else "",
            "deleted_layout": job.deleted_layout if job else "preserve",
            "rules": [Rule(path=r.path, mode=r.mode) for r in job.rules] if job else [],
            "realtime": job.realtime if job else True,
            "periodic_minutes": job.periodic_minutes if job else 0,
            "sync_on_start": job.sync_on_start if job else True,
        }
        self.title(t("wiz.edit_title") if job else t("wiz.new_title"))
        self.step = 0
        self.extra_rules = [
            {"path": rule.path, "mode": rule.mode} for rule in self.data["rules"]
        ]
        self.name_var = tk.StringVar(value=self.data["name"])
        self.source_var = tk.StringVar(value=self.data["source"])
        self.backup_var = tk.StringVar(value=self.data["backup"])
        self.deleted_var = tk.StringVar(value=self.data["deleted_store"])
        self.layout_var = tk.StringVar(value=self.data["deleted_layout"])
        self.realtime_var = tk.BooleanVar(value=self.data["realtime"])
        self.sync_on_start_var = tk.BooleanVar(value=self.data["sync_on_start"])
        minutes = self.data["periodic_minutes"]
        if minutes and minutes % 60 == 0:
            self.periodic_value_var = tk.StringVar(value=str(minutes // 60))
            self.periodic_unit_var = tk.StringVar(value=t("wiz.hours"))
        else:
            self.periodic_value_var = tk.StringVar(value=str(minutes))
            self.periodic_unit_var = tk.StringVar(value=t("wiz.minutes"))
        self.extra_mode_var = tk.StringVar(value=t("mode.ignore"))
        self.start_now_var = tk.BooleanVar(value=True)
        self.header_var = tk.StringVar()
        self.transient(master)
        self.grab_set()
        self.geometry("760x600")
        self.minsize(700, 540)
        self._build()
        self._show_step(0)

    def _build(self):
        t = self.i18n.t
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)
        outer.rowconfigure(1, weight=1)
        outer.columnconfigure(0, weight=1)
        ttk.Label(
            outer, textvariable=self.header_var, font=("Segoe UI", 12, "bold")
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.body = ttk.Frame(outer)
        self.body.grid(row=1, column=0, sticky="nsew")
        self.body.rowconfigure(0, weight=1)
        self.body.columnconfigure(0, weight=1)
        self.frames = []
        for _ in self.STEP_KEYS:
            frame = ttk.Frame(self.body, padding=4)
            frame.grid(row=0, column=0, sticky="nsew")
            self.frames.append(frame)
        self._build_step0(self.frames[0])
        self._build_step1(self.frames[1])
        self._build_step2(self.frames[2])
        self._build_step3(self.frames[3])
        self._build_step4(self.frames[4])
        self._build_step5(self.frames[5])

        footer = ttk.Frame(outer)
        footer.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self.back_btn = ttk.Button(footer, text=t("wiz.back"), command=self._back)
        self.back_btn.pack(side="left")
        ttk.Button(footer, text=t("wiz.cancel"), command=self.destroy).pack(side="right")
        self.next_btn = ttk.Button(footer, text=t("wiz.next"), command=self._next)
        self.next_btn.pack(side="right", padx=6)

    def _build_step0(self, frame):
        t = self.i18n.t
        ttk.Label(frame, text=t("wiz.name")).pack(anchor="w", pady=(4, 2))
        ttk.Entry(frame, textvariable=self.name_var).pack(fill="x")
        ttk.Label(frame, text=t("wiz.source_prompt")).pack(anchor="w", pady=(14, 2))
        row = ttk.Frame(frame)
        row.pack(fill="x")
        ttk.Entry(row, textvariable=self.source_var).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text=t("wiz.browse"), command=self._browse_source).pack(
            side="left", padx=6
        )

    def _build_step1(self, frame):
        t = self.i18n.t
        ttk.Label(frame, text=t("wiz.backup_prompt")).pack(anchor="w", pady=(4, 2))
        row = ttk.Frame(frame)
        row.pack(fill="x")
        ttk.Entry(row, textvariable=self.backup_var).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text=t("wiz.browse"), command=self._browse_backup).pack(
            side="left", padx=6
        )
        ttk.Label(frame, text=t("wiz.backup_hint"), foreground="#555").pack(
            anchor="w", pady=(10, 0)
        )

    def _build_step2(self, frame):
        t = self.i18n.t
        ttk.Label(frame, text=t("wiz.rules_hint"), justify="left").pack(
            anchor="w", pady=(4, 8)
        )
        line = ttk.Frame(frame)
        line.pack(fill="x")
        ttk.Label(line, text=t("wiz.rules_add_label")).pack(side="left")
        ttk.Combobox(
            line,
            textvariable=self.extra_mode_var,
            values=[t(key) for key, _ in RULE_MODES],
            state="readonly",
            width=30,
        ).pack(side="left", padx=6)
        ttk.Button(line, text=t("wiz.rules_add_btn"), command=self._add_extra).pack(side="left")
        ttk.Button(line, text=t("wiz.rules_remove"), command=self._remove_extra).pack(
            side="left", padx=6
        )
        self.extra_list = tk.Listbox(frame, height=12)
        self.extra_list.pack(fill="both", expand=True, pady=(8, 0))

    def _build_step3(self, frame):
        t = self.i18n.t
        ttk.Label(frame, text=t("wiz.trash_prompt")).pack(anchor="w", pady=(4, 2))
        row = ttk.Frame(frame)
        row.pack(fill="x")
        ttk.Entry(row, textvariable=self.deleted_var).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text=t("wiz.browse"), command=self._browse_deleted).pack(
            side="left", padx=6
        )
        ttk.Label(frame, text=t("wiz.trash_hint"), foreground="#555").pack(
            anchor="w", pady=(4, 0)
        )
        ttk.Label(frame, text=t("wiz.trash_layout")).pack(anchor="w", pady=(14, 2))
        ttk.Radiobutton(
            frame, text=t("wiz.layout_preserve"), variable=self.layout_var, value="preserve"
        ).pack(anchor="w")
        ttk.Radiobutton(
            frame, text=t("wiz.layout_flat"), variable=self.layout_var, value="flat"
        ).pack(anchor="w")

    def _build_step4(self, frame):
        t = self.i18n.t
        ttk.Checkbutton(
            frame, text=t("wiz.realtime"), variable=self.realtime_var
        ).pack(anchor="w", pady=(6, 2))
        ttk.Label(frame, text=t("wiz.realtime_hint"), foreground="#555").pack(
            anchor="w", pady=(0, 12)
        )
        periodic = ttk.Frame(frame)
        periodic.pack(fill="x")
        ttk.Label(periodic, text=t("wiz.periodic_prompt")).pack(side="left")
        ttk.Spinbox(
            periodic, from_=0, to=100000, width=7, textvariable=self.periodic_value_var
        ).pack(side="left", padx=6)
        ttk.Combobox(
            periodic,
            textvariable=self.periodic_unit_var,
            values=[t("wiz.minutes"), t("wiz.hours")],
            state="readonly",
            width=8,
        ).pack(side="left")
        ttk.Label(frame, text=t("wiz.periodic_zero"), foreground="#555").pack(
            anchor="w", pady=(2, 12)
        )
        ttk.Checkbutton(frame, text=t("wiz.sync_on_start"), variable=self.sync_on_start_var).pack(
            anchor="w"
        )

    def _build_step5(self, frame):
        t = self.i18n.t
        self.summary = ScrolledText(frame, height=18, state="disabled", wrap="word")
        self.summary.pack(fill="both", expand=True)
        ttk.Checkbutton(frame, text=t("wiz.start_now"), variable=self.start_now_var).pack(
            anchor="w", pady=(8, 0)
        )

    def _browse_source(self):
        chosen = filedialog.askdirectory(
            title=self.i18n.t("wiz.source_prompt"),
            initialdir=self.source_var.get() or os.path.expanduser("~"),
        )
        if chosen:
            self.source_var.set(os.path.normpath(chosen))
            if not self.name_var.get().strip():
                self.name_var.set(os.path.basename(chosen.rstrip("\\/")) or "Backup")

    def _browse_backup(self):
        chosen = filedialog.askdirectory(
            title=self.i18n.t("wiz.backup_prompt"),
            initialdir=self.backup_var.get() or os.path.expanduser("~"),
        )
        if chosen:
            self.backup_var.set(os.path.normpath(chosen))

    def _browse_deleted(self):
        chosen = filedialog.askdirectory(
            title=self.i18n.t("wiz.trash_prompt"),
            initialdir=self.deleted_var.get() or self.backup_var.get() or os.path.expanduser("~"),
        )
        if chosen:
            self.deleted_var.set(os.path.normpath(chosen))

    def _mode_display(self, mode):
        for key, value in RULE_MODES:
            if value == mode:
                return self.i18n.t(key)
        return self.i18n.t(RULE_MODES[0][0])

    def _mode_from_display(self, display):
        for key, value in RULE_MODES:
            if self.i18n.t(key) == display:
                return value
        return MODE_NORMAL

    def _refresh_extras(self):
        self.extra_list.delete(0, "end")
        if not self.extra_rules:
            self.extra_list.insert("end", self.i18n.t("wiz.rules_empty"))
            self.extra_list.itemconfigure(0, foreground="#777")
        for item in self.extra_rules:
            self.extra_list.insert(
                "end", f"{item['path']}    [{self._mode_display(item['mode'])}]"
            )

    def _add_extra(self):
        source = self.source_var.get().strip()
        chosen = filedialog.askdirectory(
            title=self.i18n.t("wiz.rules_add_btn"),
            initialdir=source if os.path.isdir(source) else os.path.expanduser("~"),
        )
        if not chosen:
            return
        chosen = os.path.normpath(chosen)
        if source and BackupEngine._within(chosen, source):
            value = os.path.relpath(chosen, source)
        else:
            value = chosen
        mode = self._mode_from_display(self.extra_mode_var.get())
        self.extra_rules.append({"path": value, "mode": mode})
        self._refresh_extras()

    def _remove_extra(self):
        selection = self.extra_list.curselection()
        for index in reversed(selection):
            if 0 <= index < len(self.extra_rules):
                del self.extra_rules[index]
        self._refresh_extras()

    def _collect_rules(self):
        return [
            Rule(path=item["path"], mode=item["mode"])
            for item in self.extra_rules
            if item["mode"] != MODE_NORMAL
        ]

    def _collect_periodic(self):
        value = self.periodic_value_var.get().strip()
        try:
            number = max(0, int(value or 0))
        except ValueError:
            number = 0
        if self.periodic_unit_var.get() == self.i18n.t("wiz.hours"):
            number *= 60
        return number

    def _show_step(self, index):
        t = self.i18n.t
        self.step = index
        self.header_var.set(
            t(
                "wiz.step_n",
                i=index + 1,
                n=len(self.STEP_KEYS),
                title=t(self.STEP_KEYS[index]),
            )
        )
        if index == 2:
            self._refresh_extras()
        if index == 5:
            self._fill_summary()
        for position, frame in enumerate(self.frames):
            if position == index:
                frame.tkraise()
        self.back_btn.configure(state="normal" if index > 0 else "disabled")
        self.next_btn.configure(
            text=t("wiz.save") if index == len(self.STEP_KEYS) - 1 else t("wiz.next")
        )

    def _validate_step(self, index):
        t = self.i18n.t
        if index == 0:
            if not self.name_var.get().strip():
                messagebox.showwarning(APP_NAME, t("wiz.warn_name"), parent=self)
                return False
            if not os.path.isdir(self.source_var.get().strip()):
                messagebox.showwarning(APP_NAME, t("wiz.warn_source"), parent=self)
                return False
        if index == 1:
            backup = self.backup_var.get().strip()
            source = self.source_var.get().strip()
            if not backup:
                messagebox.showwarning(APP_NAME, t("wiz.warn_backup"), parent=self)
                return False
            if os.path.normcase(os.path.abspath(backup)) == os.path.normcase(
                os.path.abspath(source)
            ):
                messagebox.showwarning(APP_NAME, t("wiz.warn_same"), parent=self)
                return False
        return True

    def _next(self):
        if not self._validate_step(self.step):
            return
        if self.step == 0:
            self.data["name"] = self.name_var.get().strip()
            self.data["source"] = self.source_var.get().strip()
        elif self.step == 1:
            self.data["backup"] = self.backup_var.get().strip()
            if not self.deleted_var.get().strip():
                self.deleted_var.set(os.path.join(self.data["backup"], DEFAULT_DELETED_DIRNAME))
        elif self.step == 2:
            self.data["rules"] = self._collect_rules()
        elif self.step == 3:
            self.data["deleted_store"] = self.deleted_var.get().strip()
            self.data["deleted_layout"] = self.layout_var.get() or "preserve"
        elif self.step == 4:
            self.data["realtime"] = bool(self.realtime_var.get())
            self.data["sync_on_start"] = bool(self.sync_on_start_var.get())
            self.data["periodic_minutes"] = self._collect_periodic()
        if self.step < len(self.STEP_KEYS) - 1:
            self._show_step(self.step + 1)
        else:
            self._finish()

    def _back(self):
        if self.step > 0:
            self._show_step(self.step - 1)

    def _fill_summary(self):
        t = self.i18n.t
        self.data["deleted_store"] = self.deleted_var.get().strip()
        self.data["deleted_layout"] = self.layout_var.get() or "preserve"
        self.data["realtime"] = bool(self.realtime_var.get())
        self.data["sync_on_start"] = bool(self.sync_on_start_var.get())
        self.data["periodic_minutes"] = self._collect_periodic()
        rules_text = "\n    ".join(
            f"{rule.path} -> {self._mode_display(rule.mode)}" for rule in self.data["rules"]
        )
        if self.data["periodic_minutes"]:
            if self.data["periodic_minutes"] % 60 == 0:
                schedule = t("sched.every_hours", n=self.data["periodic_minutes"] // 60)
            else:
                schedule = t("sched.every_minutes", n=self.data["periodic_minutes"])
        else:
            schedule = t("wiz.no_periodic")
        if not self.data["realtime"]:
            schedule = t("wiz.no_realtime_prefix") + schedule
        if self.data["sync_on_start"]:
            schedule += t("wiz.plus_on_start")
        rows = [
            (t("lbl.name"), self.data["name"]),
            (t("lbl.source"), self.data["source"]),
            (t("lbl.backup"), self.data["backup"]),
            (t("lbl.trash"), self.data["deleted_store"] or t("wiz.auto_trash")),
            (
                t("wiz.layout_label"),
                t("wiz.layout_path_short")
                if self.data["deleted_layout"] == "preserve"
                else t("wiz.layout_flat_short"),
            ),
            (t("lbl.schedule"), schedule),
            (t("lbl.rules"), rules_text or t("lbl.none")),
        ]
        self.summary.configure(state="normal")
        self.summary.delete("1.0", "end")
        for label, value in rows:
            self.summary.insert("end", f"{label}:\n    {value}\n\n")
        self.summary.configure(state="disabled")

    def _finish(self):
        job = self.result_job or Job()
        self.data["deleted_store"] = self.deleted_var.get().strip()
        self.data["deleted_layout"] = self.layout_var.get() or "preserve"
        self.data["realtime"] = bool(self.realtime_var.get())
        self.data["sync_on_start"] = bool(self.sync_on_start_var.get())
        self.data["periodic_minutes"] = self._collect_periodic()
        job.id = self.data["id"]
        job.name = self.data["name"] or "Task"
        job.source = self.data["source"]
        job.backup = self.data["backup"]
        job.deleted_store = self.data["deleted_store"]
        job.deleted_layout = self.data["deleted_layout"]
        job.rules = list(self.data["rules"])
        job.realtime = self.data["realtime"]
        job.sync_on_start = self.data["sync_on_start"]
        job.periodic_minutes = self.data["periodic_minutes"]
        self.on_save(job, bool(self.start_now_var.get()))
        self.destroy()
