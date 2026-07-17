# termhop agent — wire envelope model, mirrors relay-server/relay/envelope.py
# field-for-field. The agent both builds outgoing envelopes and parses
# incoming ones from the relay, so this needs the same shape/validation the
# relay itself enforces.
import json
from typing import Any

from pydantic import BaseModel, Field, ValidationError


class EnvelopeError(Exception):
    pass


class Envelope(BaseModel):
    v: int
    type: str
    session_id: str | None = None
    seq: int
    ts: int
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
