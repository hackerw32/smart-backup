"""Παράθυρο ομαδοποιημένων αποτυχιών."""

import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText

from ..constants import APP_NAME
from ..i18n import Translator
from ..logging_setup import LOGGER


class FailuresDialog(tk.Toplevel):
    def __init__(self, master, title, failures, i18n=None):
        super().__init__(master)
        self.i18n = i18n or Translator()
        self.title(title)
        self.failures = failures
        self.geometry("760x520")
        self.minsize(640, 440)
        self.transient(master)
        self.grab_set()
        t = self.i18n.t

        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)
        outer.rowconfigure(1, weight=1)
        outer.columnconfigure(0, weight=1)

        ttk.Label(outer, text=t("fail.hint")).grid(row=0, column=0, sticky="w", pady=(0, 6))

        self.tree = ttk.Treeview(
            outer, columns=("count",), show="tree headings", height=7, selectmode="browse"
        )
        self.tree.heading("#0", text=t("fail.col_reason"))
        self.tree.heading("count", text=t("fail.col_count"))
        self.tree.column("#0", width=520)
        self.tree.column("count", width=80, anchor="e")
        self.tree.grid(row=1, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", lambda event: self._show_detail())

        detail_frame = ttk.LabelFrame(outer, text=t("fail.details"), padding=6)
        detail_frame.grid(row=2, column=0, sticky="nsew", pady=(8, 0))
        detail_frame.rowconfigure(0, weight=1)
        detail_frame.columnconfigure(0, weight=1)
        self.detail = ScrolledText(detail_frame, height=10, state="disabled", wrap="word")
        self.detail.grid(row=0, column=0, sticky="nsew")

        buttons = ttk.Frame(outer)
        buttons.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(buttons, text=t("fail.copy_all"), command=self._copy_all).pack(side="left")
        ttk.Button(buttons, text=t("fail.save_log"), command=self._save_log).pack(
            side="left", padx=6
        )
        ttk.Button(buttons, text=t("fail.clear"), command=self._clear).pack(side="right")
        ttk.Button(buttons, text=t("fail.close"), command=self.destroy).pack(
            side="right", padx=6
        )

        self._populate()

    def _populate(self):
        self.tree.delete(*self.tree.get_children())
        for reason, entry in sorted(
            self.failures.items(), key=lambda item: -item[1]["count"]
        ):
            self.tree.insert(
                "", "end", iid=reason, text=self.i18n.t(reason), values=(entry["count"],)
            )
        children = self.tree.get_children()
        if children:
            self.tree.selection_set(children[0])
            self._show_detail()

    def _show_detail(self):
        selection = self.tree.selection()
        if not selection:
            return
        t = self.i18n.t
        reason = selection[0]
        entry = self.failures.get(reason, {})
        lines = [
            t("fail.reason", reason=t(reason)),
            t("fail.count", n=entry.get("count", 0)),
            "",
            t("fail.last_msg", msg=entry.get("detail", "")),
            "",
            t("fail.files"),
        ]
        for path, detail in entry.get("items", []):
            lines.append(f"  - {path}")
            if detail and detail != entry.get("detail"):
                lines.append(f"      {detail}")
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("end", "\n".join(lines))
        self.detail.configure(state="disabled")

    def _report_text(self):
        lines = []
        for reason, entry in sorted(self.failures.items(), key=lambda item: -item[1]["count"]):
            lines.append(f"[{self.i18n.t(reason)}] ({entry['count']})")
            lines.append(f"  {entry.get('detail', '')}")
            for path, detail in entry.get("items", []):
                lines.append(f"  - {path}")
            lines.append("")
        return "\n".join(lines).strip() or self.i18n.t("fail.empty")

    def _copy_all(self):
        t = self.i18n.t
        try:
            self.clipboard_clear()
            self.clipboard_append(self._report_text())
            messagebox.showinfo(APP_NAME, t("fail.copied"), parent=self)
        except tk.TclError as exc:
            messagebox.showerror(APP_NAME, t("fail.copy_failed", error=exc), parent=self)

    def _save_log(self):
        t = self.i18n.t
        path = filedialog.asksaveasfilename(
            parent=self,
            title=t("fail.save_title"),
            defaultextension=".log",
            initialfile="smart_backup_failures.log",
            filetypes=[(t("fail.log_file"), "*.log"), (t("fail.all_files"), "*.*")],
        )
        if not path:
            return
        try:
            stamp = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(f"\n===== {APP_NAME} - {stamp} =====\n")
                fh.write(self._report_text())
                fh.write("\n")
            LOGGER.warning("Failure report: %s", self._report_text().replace("\n", " | "))
            messagebox.showinfo(APP_NAME, t("fail.saved", path=path), parent=self)
        except OSError as exc:
            messagebox.showerror(APP_NAME, t("fail.save_failed", error=exc), parent=self)

    def _clear(self):
        self.failures.clear()
        self._populate()
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.configure(state="disabled")
