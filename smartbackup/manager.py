"""Διαχείριση των engines ανά εργασία."""

from .engine import BackupEngine


class JobManager:
    def __init__(self, app):
        self.app = app
        self.engines = {}

    def engine(self, job):
        engine = self.engines.get(job.id)
        if engine is None:
            engine = BackupEngine(
                job,
                self.app.on_engine_log,
                self.app.on_engine_progress,
                self.app.on_engine_status,
                self.app.on_engine_failure,
                translator=self.app.i18n,
            )
            self.engines[job.id] = engine
        return engine

    def is_running(self, job):
        engine = self.engines.get(job.id)
        return bool(engine and engine.is_running())

    def start(self, job):
        return self.engine(job).start()

    def stop(self, job):
        engine = self.engines.get(job.id)
        if engine:
            engine.stop()

    def start_all(self, jobs):
        errors = []
        for job in jobs:
            try:
                self.engine(job).start()
            except Exception as exc:
                errors.append((job, str(exc)))
        return errors

    def stop_all(self, jobs):
        for job in jobs:
            self.stop(job)

    def forget(self, job_id):
        engine = self.engines.pop(job_id, None)
        if engine:
            try:
                engine.stop()
            except Exception:
                pass

    def stop_all_engines(self):
        for engine in list(self.engines.values()):
            try:
                engine.stop()
            except Exception:
                pass
