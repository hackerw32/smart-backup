"""Λίστα εργασιών με checkboxes, multi-select και δεξί κλικ."""

import tkinter as tk
from tkinter import ttk

CHECK_ON = "\u2611"
CHECK_OFF = "\u2610"


class TaskTree(ttk.Frame):
    def __init__(self, master, on_select, on_activate, on_context, on_check_change=None):
        super().__init__(master)
        self.on_select = on_select
        self.on_activate = on_activate
        self.on_context = on_context
        self.on_check_change = on_check_change
        self.checked = set()
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(
            self,
            columns=("check", "name", "status"),
            show="headings",
            selectmode="extended",
        )
        self.tree.heading("check", text="")
        self.tree.heading("name", text="")
        self.tree.heading("status", text="")
        self.tree.column("check", width=34, anchor="center", stretch=False)
        self.tree.column("name", width=220, anchor="w")
        self.tree.column("status", width=180, anchor="w", stretch=False)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.tag_configure("running", foreground="#127a12")
        self.tree.tag_configure("stopped", foreground="#666666")
        self.tree.tag_configure("error", foreground="#b00020")
        self.tree.bind("<<TreeviewSelect>>", lambda event: self.on_select())
        self.tree.bind("<Button-1>", self._on_left_click)
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Button-3>", self._on_right_click)

    def set_headings(self, task_text, status_text):
        self.tree.heading("name", text=task_text)
        self.tree.heading("status", text=status_text)

    def clear(self):
        self.tree.delete(*self.tree.get_children())

    def insert_task(self, job_id, name, status, checked=False, tag="stopped"):
        if checked:
            self.checked.add(job_id)
        mark = CHECK_ON if job_id in self.checked else CHECK_OFF
        self.tree.insert("", "end", iid=job_id, values=(mark, name, status), tags=(tag,))

    def update_name(self, job_id, name):
        if self.tree.exists(job_id):
            values = list(self.tree.item(job_id, "values"))
            values[1] = name
            self.tree.item(job_id, values=values)

    def set_status(self, job_id, status, tag=None):
        if not self.tree.exists(job_id):
            return
        values = list(self.tree.item(job_id, "values"))
        values[2] = status
        self.tree.item(job_id, values=values)
        if tag:
            self.tree.item(job_id, tags=(tag,))

    def get_status(self, job_id):
        if not self.tree.exists(job_id):
            return None
        return self.tree.item(job_id, "values")[2]

    def is_checked(self, job_id):
        return job_id in self.checked

    def checked_ids(self):
        return [iid for iid in self.tree.get_children() if iid in self.checked]

    def selected_ids(self):
        return list(self.tree.selection())

    def focus_row(self):
        focus = self.tree.focus()
        if focus:
            return focus
        selection = self.tree.selection()
        return selection[0] if selection else None

    def set_all_checked(self, value):
        for job_id in self.tree.get_children():
            self._set_check(job_id, value)

    def _set_check(self, job_id, value):
        if value:
            self.checked.add(job_id)
        else:
            self.checked.discard(job_id)
        if self.tree.exists(job_id):
            values = list(self.tree.item(job_id, "values"))
            values[0] = CHECK_ON if value else CHECK_OFF
            self.tree.item(job_id, values=values)
        if self.on_check_change:
            self.on_check_change()

    def _toggle_check(self, job_id):
        self._set_check(job_id, job_id not in self.checked)

    def _on_left_click(self, event):
        column = self.tree.identify_column(event.x)
        row = self.tree.identify_row(event.y)
        if row and column == "#1":
            self._toggle_check(row)
            return "break"

    def _on_double_click(self, event):
        column = self.tree.identify_column(event.x)
        row = self.tree.identify_row(event.y)
        if row and column != "#1":
            self.tree.selection_set(row)
            self.on_activate(row)
        return "break"

    def _on_right_click(self, event):
        row = self.tree.identify_row(event.y)
        if row:
            if row not in self.tree.selection() and row not in self.checked:
                self.tree.selection_set(row)
            self.tree.focus(row)
        self.on_context(event)
        return "break"
