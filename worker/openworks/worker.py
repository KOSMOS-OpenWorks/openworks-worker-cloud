"""
OpenWorks Worker Daemon — picks jobs, dispatches to executors, reports status.
"""

import logging
import signal
import threading
from datetime import datetime

from .client import ControlClient, JobAssignment
from .fs import JobFS

logger = logging.getLogger("openworks.worker")


class Worker:
    """Main worker daemon with poll loop and job dispatch."""

    def __init__(self, client: ControlClient, executors: dict, pipelines: dict | None = None):
        """
        Args:
            client: ControlClient for polling
            executors: dict of job_type → callable(fs, job) returning status dict
            pipelines: optional dict of pipeline definitions to register with the server
        """
        self.client = client
        self.executors = executors
        self.pipelines = pipelines
        self._registered = False
        self._running = True
        self._active_jobs: dict[str, threading.Thread] = {}
        self._job_status: dict[str, dict] = {}  # job_id → status to report
        self._lock = threading.Lock()

        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def run(self):
        """Main poll loop — runs until stopped."""
        logger.info("worker starting, pick=%s, capacity=%d",
                     self.client.pick, self.client.capacity)

        while self._running:
            try:
                self._tick()
            except PermissionError:
                logger.error("authentication failed, stopping")
                break
            except Exception:
                logger.exception("poll tick failed")

            self.client.wait()

        logger.info("worker stopped, waiting for active jobs...")
        for t in self._active_jobs.values():
            t.join(timeout=10)

    def _tick(self):
        # Collect status reports
        with self._lock:
            status_reports = list(self._job_status.values())
            # Clear completed/failed reports after sending
            self._job_status = {
                jid: s for jid, s in self._job_status.items()
                if s.get("status") not in ("completed", "failed")
            }

        # Send pipeline definitions on first poll
        data = None
        if self.pipelines and not self._registered:
            data = {"pipelines": self.pipelines}

        result = self.client.poll(status=status_reports, data=data)
        if data and result.slots:
            self._registered = True
            logger.info("registered %d pipeline(s) with server", len(self.pipelines))

        # Handle cancellations
        for job_id in result.cancellations:
            self._cancel_job(job_id)

        # Dispatch new assignments
        for assignment in result.assignments:
            self._dispatch(assignment)

    def _dispatch(self, assignment: JobAssignment):
        job_id = assignment.job_id
        job_type = assignment.job_type

        if job_type not in self.executors:
            logger.warning("no executor for job type %s, reporting failed", job_type)
            with self._lock:
                self._job_status[job_id] = {
                    "jobId": job_id,
                    "status": "failed",
                    "error": f"no executor for type: {job_type}",
                }
            return

        t = threading.Thread(
            target=self._run_job,
            args=(assignment,),
            name=f"job-{job_id}",
            daemon=True,
        )

        with self._lock:
            self._active_jobs[job_id] = t

        t.start()

    def _run_job(self, assignment: JobAssignment):
        job_id = assignment.job_id
        logger.info("starting job %s (type=%s)", job_id, assignment.job_type)

        try:
            # TLS settings from control client
            verify_tls = getattr(self.client, '_session', None)
            tls_verify = self.client._session.verify if self.client._session else True

            # Build JobFS from origin share
            # Check assignment-level first, then fall back to job params
            origin = assignment.origin or assignment.params.get("origin") or {}
            origin_url = origin.get("webdav_url", "") or assignment.params.get("origin_url", "")
            origin_token = origin.get("password", origin.get("token", "")) or assignment.params.get("origin_password", "")
            fs = JobFS(
                webdav_url=origin_url,
                token=origin_token,
                deadline=assignment.valid_till,
                verify_tls=tls_verify,
            )

            # Build destination FS if different from origin
            dest_info = assignment.destination or assignment.params.get("destination")
            dest_fs = None
            if dest_info:
                dest_fs = JobFS(
                    webdav_url=dest_info.get("webdav_url", ""),
                    token=dest_info.get("password", dest_info.get("token", "")),
                    deadline=assignment.valid_till,
                    verify_tls=tls_verify,
                )

            executor = self.executors[assignment.job_type]

            # Stage callback — executor calls this to report progress
            def on_stage(stage: str, progress: int = 0):
                with self._lock:
                    self._job_status[job_id] = {
                        "jobId": job_id,
                        "progress": progress,
                        "stage": stage,
                    }

            on_stage("starting", 5)

            result = executor(
                fs=fs,
                dest_fs=dest_fs,
                params=assignment.params,
                job_id=job_id,
                on_stage=on_stage,
            )

            with self._lock:
                self._job_status[job_id] = {
                    "jobId": job_id,
                    "status": "completed",
                    "result": result or {},
                }

            logger.info("job %s completed", job_id)

        except Exception as e:
            logger.exception("job %s failed", job_id)
            with self._lock:
                self._job_status[job_id] = {
                    "jobId": job_id,
                    "status": "failed",
                    "error": str(e),
                }

        finally:
            with self._lock:
                self._active_jobs.pop(job_id, None)

    def _cancel_job(self, job_id: str):
        logger.info("cancelling job %s", job_id)
        with self._lock:
            t = self._active_jobs.get(job_id)
            if t:
                # Thread-based cancellation is limited — the executor
                # should check deadline/validity periodically
                self._job_status[job_id] = {
                    "jobId": job_id,
                    "status": "failed",
                    "error": "cancelled by cloud",
                }

    def _handle_signal(self, signum, frame):
        logger.info("received signal %d, stopping", signum)
        self._running = False
