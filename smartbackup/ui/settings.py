"""Παράθυρο ρυθμίσεων (γλώσσα, αυτόματη έναρξη, έλεγχος ενημερώσεων)."""

import threading
import webbrowser
import tkinter as tk
from tkinter import ttk

from ..constants import VERSION, RELEASES_URL
from ..i18n import LANGUAGES
from ..updates import check_for_updates


class SettingsDialog(tk.Toplevel):
    def __init__(self, master, i18n, autostart, on_save):
        super().__init__(master)
        self.i18n = i18n
        self.on_save = on_save
        self._release_url = RELEASES_URL
        self.title(i18n.t("set.title"))
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self.language_var = tk.StringVar()
        self.autostart_var = tk.BooleanVar(value=bool(autostart))
        self.update_result = tk.StringVar(value="")
        self._display_to_code = {name: code for name, code in LANGUAGES}
        self._code_to_display = {code: name for name, code in LANGUAGES}
        self.language_var.set(self._code_to_display.get(i18n.language, LANGUAGES[0][0]))

        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)

        lang_row = ttk.Frame(outer)
        lang_row.pack(fill="x")
        ttk.Label(lang_row, text=i18n.t("set.language"), width=12).pack(side="left")
        ttk.Combobox(
            lang_row,
            textvariable=self.language_var,
            values=[name for name, _ in LANGUAGES],
            state="readonly",
            width=18,
        ).pack(side="left")

        ttk.Checkbutton(
            outer, text=i18n.t("set.autostart"), variable=self.autostart_var
        ).pack(anchor="w", pady=(12, 0))
        ttk.Label(outer, text=i18n.t("set.language_hint"), foreground="#555").pack(
            anchor="w", pady=(8, 0)
        )

        ttk.Separator(outer, orient="horizontal").pack(fill="x", pady=12)
        ttk.Label(outer, text=i18n.t("set.version", version=VERSION)).pack(anchor="w")
        update_row = ttk.Frame(outer)
        update_row.pack(fill="x", pady=(8, 0))
        ttk.Button(
            update_row, text=i18n.t("set.check_updates"), command=self._check_updates
        ).pack(side="left")
        self.release_btn = ttk.Button(
            update_row, text=i18n.t("set.open_release"), command=self._open_release,
            state="disabled",
        )
        self.release_btn.pack(side="left", padx=6)
        ttk.Label(
            outer, textvariable=self.update_result, foreground="#333", wraplength=420,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=(16, 0))
        ttk.Button(buttons, text=i18n.t("wiz.save"), command=self._apply).pack(side="right")
        ttk.Button(buttons, text=i18n.t("wiz.cancel"), command=self.destroy).pack(
            side="right", padx=6
        )

    def _check_updates(self):
        self.update_result.set(self.i18n.t("set.checking"))
        self.release_btn.configure(state="disabled")
        threading.Thread(target=self._run_check, daemon=True).start()

    def _run_check(self):
        result = check_for_updates(VERSION)
        try:
            self.after(0, lambda: self._show_result(result))
        except tk.TclError:
            pass

    def _show_result(self, result):
        state = result.get("status")
        if state == "ok":
            if result.get("update"):
                self._release_url = result.get("url") or RELEASES_URL
                self.update_result.set(
                    self.i18n.t("set.update_available", version=result.get("latest", ""))
                )
                self.release_btn.configure(state="normal")
            else:
                self.update_result.set(self.i18n.t("set.up_to_date"))
        elif state == "no_releases":
            self.update_result.set(self.i18n.t("set.no_releases"))
        else:
            self.update_result.set(
                self.i18n.t("set.update_error", error=result.get("error", ""))
            )

    def _open_release(self):
        try:
            webbrowser.open(self._release_url)
        except Exception:
            pass

    def _apply(self):
        code = self._display_to_code.get(self.language_var.get(), self.i18n.language)
        self.on_save(code, bool(self.autostart_var.get()))
        self.destroy()
