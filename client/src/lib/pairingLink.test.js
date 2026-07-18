import { describe, expect, it } from "vitest";
import { PairingLinkError, decodePairingLink, encodePairingLink } from "./pairingLink.js";

describe("pairingLink", () => {
  const authenticated = {
    pairingSecret: "secret-value",
    agentPubkey: "agent-public-key",
    sessionId: "sess-1",
  };

  it("round-trips relay/token/hostname", () => {
    const link = encodePairingLink({
      relayUrl: "wss://relay.example.com", token: "tok_abc123", hostname: "my-box", ...authenticated,
    });
    expect(link.startsWith("termhop://pair?")).toBe(true);
    const decoded = decodePairingLink(link);
    expect(decoded).toEqual({
      relayUrl: "wss://relay.example.com", token: "tok_abc123", hostname: "my-box", ...authenticated,
    });
  });

  it("omits hostname field when not given", () => {
    const link = encodePairingLink({ relayUrl: "ws://localhost:8080", token: "tok_abc", ...authenticated });
    const decoded = decodePairingLink(link);
    expect(decoded.hostname).toBe("");
  });

  it("percent-encodes the relay URL", () => {
    const link = encodePairingLink({ relayUrl: "wss://relay.example.com:8080/x?y=1", token: "t", ...authenticated });
    expect(link).not.toContain("wss://relay.example.com:8080/x?y=1");
    const decoded = decodePairingLink(link);
    expect(decoded.relayUrl).toBe("wss://relay.example.com:8080/x?y=1");
  });

  it("rejects a non-termhop link", () => {
    expect(() => decodePairingLink("https://example.com/pair?token=x")).toThrow(PairingLinkError);
  });

  it("rejects a malformed URL", () => {
    expect(() => decodePairingLink("not a url at all")).toThrow(PairingLinkError);
  });

  it("rejects plaintext non-loopback relay URLs", () => {
    const link = encodePairingLink({ relayUrl: "ws://relay.example.com", token: "t", ...authenticated });
    expect(() => decodePairingLink(link)).toThrow(/wss/);
  });

  it("rejects a link missing token", () => {
    expect(() => decodePairingLink("termhop://pair?relay=ws%3A%2F%2Fx")).toThrow(PairingLinkError);
  });

  it("throws when encoding without relayUrl or token", () => {
    expect(() => encodePairingLink({ token: "t", ...authenticated })).toThrow(PairingLinkError);
    expect(() => encodePairingLink({ relayUrl: "ws://x", ...authenticated })).toThrow(PairingLinkError);
  });
});
