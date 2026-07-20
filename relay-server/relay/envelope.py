# termhop relay — wire envelope model. The relay validates shape/size only;
# it never inspects `payload` contents for any message type.
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from relay.errors import EnvelopeInvalid, EnvelopeTooLarge, ProtocolVersionMismatch

PAIRING_TYPES = {
    "pair_init",
    "pair_request",
    "pair_challenge",
    "pair_complete",
    "resume_init",
    "resume_request",
    "resume_challenge",
    "resume_proof",
    "resume_complete",
}
SESSION_CONTROL_TYPES = {
    "session_list",
    "session_open",
    "session_resize",
    "session_close",
    "idle_alert",
}
TERMINAL_DATA_TYPES = {"pty_data", "pty_input", "device_credential"}
PORT_FORWARD_TYPES = {"port_forward_request", "port_forward_data", "port_forward_close"}

ROUTABLE_TYPES = SESSION_CONTROL_TYPES | TERMINAL_DATA_TYPES | PORT_FORWARD_TYPES


class Envelope(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    v: int = Field(ge=1, le=255)
    type: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    session_id: str | None = Field(default=None, max_length=69)
    seq: int = Field(ge=0, le=2**53 - 1)
    ts: int = Field(ge=0, le=2**63 - 1)
    payload: dict[str, Any] = Field(default_factory=dict)


def parse_envelope(
    raw: bytes | str, *, max_bytes: int, expected_version: int
) -> Envelope:
    """Decode and validate one wire message. Raises EnvelopeTooLarge,
    EnvelopeInvalid, or ProtocolVersionMismatch — never returns a partially
    valid envelope."""
    size = len(raw) if isinstance(raw, bytes) else len(raw.encode("utf-8"))
    if size > max_bytes:
        raise EnvelopeTooLarge(f"envelope of {size} bytes exceeds cap of {max_bytes}")

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise EnvelopeInvalid(f"invalid JSON: {exc}") from exc

    try:
        envelope = Envelope.model_validate(data)
    except ValidationError as exc:
        raise EnvelopeInvalid(f"invalid envelope shape: {exc}") from exc

    if envelope.v != expected_version:
        raise ProtocolVersionMismatch(got=envelope.v, expected=expected_version)

    return envelope


def dump_envelope(envelope: Envelope) -> str:
    return envelope.model_dump_json()
