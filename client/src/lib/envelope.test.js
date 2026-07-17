import { describe, expect, it } from "vitest";
import { EnvelopeError, buildEnvelope, dumpEnvelope, parseEnvelope } from "./envelope.js";

describe("envelope", () => {
  it("round-trips through JSON", () => {
    const envelope = buildEnvelope("pty_data", {
      sessionId: "sess-1",
      seq: 1,
      payload: { nonce: "a", ciphertext: "b" },
    });
    const raw = dumpEnvelope(envelope);
    const parsed = parseEnvelope(raw);
    expect(parsed.type).toBe("pty_data");
    expect(parsed.session_id).toBe("sess-1");
    expect(parsed.payload).toEqual({ nonce: "a", ciphertext: "b" });
  });

  it("allows null session_id for pre-pairing messages", () => {
    const envelope = buildEnvelope("pair_request", { seq: 1, payload: { token: "x" } });
    expect(envelope.session_id).toBeNull();
    const parsed = parseEnvelope(dumpEnvelope(envelope));
    expect(parsed.session_id).toBeNull();
  });

  it("defaults payload to an empty object when absent", () => {
    const parsed = parseEnvelope(JSON.stringify({ v: 1, type: "pair_complete", session_id: "s1", seq: 1, ts: 1 }));
    expect(parsed.payload).toEqual({});
  });

  it("rejects malformed JSON", () => {
    expect(() => parseEnvelope("not json")).toThrow(EnvelopeError);
  });

  it("rejects missing required fields", () => {
    expect(() => parseEnvelope(JSON.stringify({ v: 1, type: "pair_init" }))).toThrow(EnvelopeError);
  });

  it("requires an explicit numeric seq when building", () => {
    expect(() => buildEnvelope("pair_request", { payload: {} })).toThrow(EnvelopeError);
  });
});
