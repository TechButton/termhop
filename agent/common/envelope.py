# termhop agent — wire envelope model, mirrors relay-server/relay/envelope.py
# field-for-field. The agent both builds outgoing envelopes and parses
# incoming ones from the relay, so this needs the same shape/validation the
# relay itself enforces.
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class EnvelopeError(Exception):
    pass


class Envelope(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    v: int = Field(ge=1, le=255)
    type: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    session_id: str | None = Field(default=None, max_length=69)
    seq: int = Field(ge=0, le=2**53 - 1)
    ts: int = Field(ge=0, le=2**63 - 1)
    payload: dict[str, Any] = Field(default_factory=dict)


def parse_envelope(raw: bytes | str) -> Envelope:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise EnvelopeError(f"invalid JSON: {exc}") from exc

    try:
        return Envelope.model_validate(data)
    except ValidationError as exc:
        raise EnvelopeError(f"invalid envelope shape: {exc}") from exc


def dump_envelope(envelope: Envelope) -> str:
    return envelope.model_dump_json()
