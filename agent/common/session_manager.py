"""Local persistent metadata and control leases for terminal sessions.

This module deliberately does not own a PTY yet. It establishes the lifecycle
and single-controller invariants that the PTY supervisor and relay protocol
will use, while keeping the manifest free of terminal output and credentials.
"""

import json
import os
import re
import secrets
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

SessionState = Literal["created", "running", "detached", "paused", "exited", "terminated"]
_SESSION_ID_RE = re.compile(r"^ts-[a-f0-9]{32}$")
_MAX_LABEL = 96
_MAX_CWD = 4096


class SessionError(ValueError):
    pass


@dataclass
class SessionRecord:
    session_id: str
    label: str
    cwd: str
    state: SessionState
    created_at: int
    updated_at: int
    exit_code: int | None = None


@dataclass
class _Lease:
    token: str
    expires_at: float


class SessionManager:
    """Own bounded session metadata and ephemeral browser control leases."""

    def __init__(self, manifest_path: Path | None = None, *, lease_seconds: int = 300):
        if not 30 <= lease_seconds <= 3600:
            raise SessionError("lease_seconds must be between 30 and 3600")
        self.manifest_path = manifest_path
        self.lease_seconds = lease_seconds
        self._sessions: dict[str, SessionRecord] = {}
        self._leases: dict[str, _Lease] = {}
        if manifest_path:
            self._load()

    @staticmethod
    def _validate_text(value: str, label: str, maximum: int) -> str:
        if not isinstance(value, str) or not value.strip() or len(value) > maximum:
            raise SessionError(f"{label} is required and must be at most {maximum} characters")
        if any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise SessionError(f"{label} contains a control character")
        return value.strip()

    def _load(self) -> None:
        assert self.manifest_path is not None
        try:
            raw = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        for item in raw if isinstance(raw, list) else []:
            try:
                record = SessionRecord(**item)
                if _SESSION_ID_RE.fullmatch(record.session_id):
                    self._sessions[record.session_id] = record
            except (TypeError, ValueError):
                continue

    def _save(self) -> None:
        if self.manifest_path is None:
            return
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(prefix=".sessions-", dir=self.manifest_path.parent)
        temporary = Path(temporary_name)
        try:
            if os.name != "nt":
                os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                fd = -1
                json.dump([asdict(item) for item in self._sessions.values()], handle, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.manifest_path)
        except BaseException:
            if fd >= 0:
                os.close(fd)
            temporary.unlink(missing_ok=True)
            raise

    def create(self, label: str, cwd: str) -> SessionRecord:
        label = self._validate_text(label, "label", _MAX_LABEL)
        cwd = self._validate_text(cwd, "cwd", _MAX_CWD)
        now = int(time.time())
        record = SessionRecord(
            session_id=f"ts-{secrets.token_hex(16)}",
            label=label,
            cwd=cwd,
            state="created",
            created_at=now,
            updated_at=now,
        )
        self._sessions[record.session_id] = record
        self._save()
        return record

    def get(self, session_id: str) -> SessionRecord:
        record = self._sessions.get(session_id)
        if record is None or not _SESSION_ID_RE.fullmatch(session_id):
            raise SessionError("session not found")
        return record

    def list(self) -> list[SessionRecord]:
        return list(self._sessions.values())

    def rename(self, session_id: str, label: str) -> SessionRecord:
        record = self.get(session_id)
        record.label = self._validate_text(label, "label", _MAX_LABEL)
        record.updated_at = int(time.time())
        self._save()
        return record

    def start(self, session_id: str) -> SessionRecord:
        record = self.get(session_id)
        if record.state not in {"created", "detached"}:
            raise SessionError(f"cannot start a {record.state} session")
        record.state = "running"
        record.updated_at = int(time.time())
        self._save()
        return record

    def attach(self, session_id: str) -> str:
        record = self.get(session_id)
        self._expire_lease(session_id)
        if record.state in {"exited", "terminated"}:
            raise SessionError(f"cannot attach to a {record.state} session")
        if session_id in self._leases:
            raise SessionError("session is locked by another browser")
        token = secrets.token_urlsafe(24)
        self._leases[session_id] = _Lease(token, time.monotonic() + self.lease_seconds)
        if record.state == "created":
            record.state = "running"
            record.updated_at = int(time.time())
            self._save()
        return token

    def detach(self, session_id: str, lease_token: str) -> SessionRecord:
        record = self.get(session_id)
        self._require_lease(session_id, lease_token)
        del self._leases[session_id]
        if record.state == "running":
            record.state = "detached"
            record.updated_at = int(time.time())
            self._save()
        return record

    def pause(self, session_id: str, lease_token: str) -> SessionRecord:
        record = self.get(session_id)
        self._require_lease(session_id, lease_token)
        if record.state != "running":
            raise SessionError(f"cannot pause a {record.state} session")
        record.state = "paused"
        record.updated_at = int(time.time())
        self._save()
        return record

    def resume(self, session_id: str, lease_token: str) -> SessionRecord:
        record = self.get(session_id)
        self._require_lease(session_id, lease_token)
        if record.state != "paused":
            raise SessionError(f"cannot resume a {record.state} session")
        record.state = "running"
        record.updated_at = int(time.time())
        self._save()
        return record

    def terminate(self, session_id: str, lease_token: str) -> SessionRecord:
        record = self.get(session_id)
        self._require_lease(session_id, lease_token)
        record.state = "terminated"
        record.updated_at = int(time.time())
        del self._leases[session_id]
        self._save()
        return record

    def _expire_lease(self, session_id: str) -> None:
        lease = self._leases.get(session_id)
        if lease and lease.expires_at <= time.monotonic():
            del self._leases[session_id]

    def _require_lease(self, session_id: str, token: str) -> None:
        self._expire_lease(session_id)
        lease = self._leases.get(session_id)
        if lease is None or not secrets.compare_digest(lease.token, token):
            raise SessionError("session control lease is invalid or expired")
