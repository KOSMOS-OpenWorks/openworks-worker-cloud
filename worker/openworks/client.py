"""
OpenWorks Control Client — Poll-based communication with OpenCloud engine.

Handles the bidirectional poll loop: sends heartbeat + status,
receives job assignments + cancellations.
"""

import time
import logging
from dataclasses import dataclass, field
from datetime import datetime

import requests

logger = logging.getLogger("openworks.client")


@dataclass
class JobAssignment:
    job_id: str
    job_type: str
    timeout: int
    valid_till: datetime
    params: dict
    origin: dict | None = None
    destination: dict | None = None


@dataclass
class PollResult:
    assignments: list[JobAssignment] = field(default_factory=list)
    cancellations: list[str] = field(default_factory=list)
    slots: dict[str, int] = field(default_factory=dict)
    denied: list[str] = field(default_factory=list)
    poll_interval_min: int = 2
    poll_interval_max: int = 30


class ControlClient:
    """Client for the OpenWorks poll endpoint."""

    def __init__(self, base_url: str, user: str, token: str,
                 pick: list[str], capacity: int = 1,
                 verify_tls: bool = True, ca_cert: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.poll_url = f"{self.base_url}/api/v0/jobs/workers/poll"
        self.pick = pick
        self.capacity = capacity
        self._session = requests.Session()
        # App token auth: username + token as password (basic auth)
        self._session.auth = (user, token)
        self._session.verify = ca_cert if ca_cert else verify_tls
        self._interval = 5  # start in the middle

    def poll(self, status: list[dict] | None = None, data: dict | None = None) -> PollResult:
        """Execute one poll tick. Returns assignments, cancellations, and matrix info."""
        body = {
            "pick": self.pick,
            "capacity": self.capacity,
            "status": status or [],
        }
        if data:
            body["data"] = data

        try:
            resp = self._session.post(self.poll_url, json=body, timeout=30)
        except requests.ConnectionError:
            logger.warning("poll: connection error, backing off")
            self._backoff()
            return PollResult()
        except requests.Timeout:
            logger.warning("poll: timeout, backing off")
            self._backoff()
            return PollResult()

        if resp.status_code == 429:
            logger.info("poll: 429 backpressure, slowing down")
            self._interval = min(self._interval * 2, 60)
            return PollResult()

        if resp.status_code == 401:
            logger.error("poll: 401 unauthorized, token invalid")
            raise PermissionError("invalid or expired token")

        if resp.status_code == 403:
            data = resp.json()
            logger.warning("poll: 403 no types allowed, denied=%s", data.get("denied"))
            return PollResult(denied=data.get("denied", []))

        if resp.status_code == 503:
            logger.warning("poll: 503 service unavailable, backing off")
            self._backoff()
            return PollResult()

        resp.raise_for_status()
        data = resp.json()

        # Update interval from server config
        config = data.get("config", {})
        poll_min = config.get("poll_interval_min", 2)
        poll_max = config.get("poll_interval_max", 30)

        result = PollResult(
            slots=data.get("slots") or {},
            denied=data.get("denied") or [],
            cancellations=data.get("cancel") or [],
            poll_interval_min=poll_min,
            poll_interval_max=poll_max,
        )

        for a in (data.get("assign") or []):
            job = a.get("job", {})
            valid_till_str = a.get("validTill", "")
            try:
                valid_till = datetime.fromisoformat(valid_till_str)
            except (ValueError, TypeError):
                valid_till = datetime.max

            result.assignments.append(JobAssignment(
                job_id=a["jobId"],
                job_type=job.get("type", ""),
                timeout=a.get("timeout", 0),
                valid_till=valid_till,
                params=job.get("params", {}),
                origin=a.get("origin"),
                destination=a.get("destination"),
            ))

        # Adjust interval: active = faster, idle = slower
        if result.assignments:
            self._interval = max(poll_min, 2)
        else:
            self._interval = min(self._interval + 1, poll_max)

        return result

    def wait(self):
        """Wait for the current poll interval."""
        time.sleep(self._interval)

    def _backoff(self):
        self._interval = min(self._interval * 2, 60)
