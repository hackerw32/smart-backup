"""Μόνιμο index (SQLite) με ό,τι έχουμε συγχρονίσει, για γρήγορη εκκίνηση."""

import os
import sqlite3

from .constants import DATA_DIR

INDEX_DIR = os.path.join(DATA_DIR, "index")


class SyncIndex:
    def __init__(self, job_id):
        self.path = os.path.join(INDEX_DIR, f"{job_id}.db")
        self.conn = None
        try:
            os.makedirs(INDEX_DIR, exist_ok=True)
            self.conn = sqlite3.connect(self.path, timeout=15)
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=NORMAL")
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS entries (rel TEXT PRIMARY KEY, is_dir INTEGER)"
            )
            self.conn.commit()
        except (OSError, sqlite3.Error):
            self.conn = None

    @property
    def available(self):
        return self.conn is not None

    def load(self):
        if not self.available:
            return {}
        try:
            rows = self.conn.execute("SELECT rel, is_dir FROM entries")
            return {rel: bool(is_dir) for rel, is_dir in rows}
        except sqlite3.Error:
            return {}

    def upsert(self, entries):
        if not self.available or not entries:
            return
        try:
            self.conn.executemany(
                "INSERT INTO entries(rel, is_dir) VALUES(?, ?) "
                "ON CONFLICT(rel) DO UPDATE SET is_dir=excluded.is_dir",
                entries,
            )
        except sqlite3.Error:
            pass

    def delete(self, rels):
        if not self.available or not rels:
            return
        try:
            self.conn.executemany("DELETE FROM entries WHERE rel=?", ((r,) for r in rels))
        except sqlite3.Error:
            pass

    def clear(self):
        if self.available:
            try:
                self.conn.execute("DELETE FROM entries")
            except sqlite3.Error:
                pass

    def commit(self):
        if self.available:
            try:
                self.conn.commit()
            except sqlite3.Error:
                pass

    def close(self):
        if self.available:
            try:
                self.conn.close()
            except sqlite3.Error:
                pass
            self.conn = None
