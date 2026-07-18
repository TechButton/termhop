// termhop client — wire envelope helpers, mirrors agent/common/envelope.py
// and relay-server/relay/envelope.py field-for-field: {v, type, session_id,
// seq, ts, payload}. Callers (RelayClient) own their own seq counter — this
// module has no hidden state, matching the Python side's explicit `seq` arg.

export class EnvelopeError extends Error {}

export function buildEnvelope(type, { sessionId = null, seq, payload = {} } = {}) {
  if (typeof seq !== "number") {
    throw new EnvelopeError("buildEnvelope requires a numeric seq");
  }
  return {
    v: 2,
    type,
    session_id: sessionId,
    seq,
    ts: Date.now(),
    payload,
  };
}

export function parseEnvelope(raw) {
  let data;
  try {
    data = typeof raw === "string" ? JSON.parse(raw) : raw;
  } catch (err) {
    throw new EnvelopeError(`invalid JSON: ${err.message}`);
  }

  if (
    typeof data !== "object" ||
    data === null ||
    typeof data.v !== "number" ||
    typeof data.type !== "string" ||
    typeof data.seq !== "number" ||
    typeof data.ts !== "number" ||
    (data.session_id !== null && data.session_id !== undefined && typeof data.session_id !== "string")
  ) {
    throw new EnvelopeError("invalid envelope shape");
  }

  return {
    v: data.v,
    type: data.type,
    session_id: data.session_id ?? null,
    seq: data.seq,
    ts: data.ts,
    payload: data.payload ?? {},
  };
}

export function dumpEnvelope(envelope) {
  return JSON.stringify(envelope);
}
