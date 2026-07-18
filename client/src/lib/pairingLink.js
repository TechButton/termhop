// termhop client — encode/decode the termhop://pair pairing link/QR
// payload. Protocol v2 carries a relay routing token plus an out-of-band
// secret, pinned agent key, and session ID. The secret is never sent to the
// relay in a WebSocket envelope.
//
// Keeping this as an explicit query string makes pasted links inspectable;
// URLSearchParams handles encoding of relay URLs and base64 public keys.

export class PairingLinkError extends Error {}

export function encodePairingLink({
  relayUrl,
  token,
  pairingSecret,
  agentPubkey,
  sessionId,
  hostname = "",
}) {
  if (!relayUrl || !token || !pairingSecret || !agentPubkey || !sessionId) {
    throw new PairingLinkError("relayUrl, token, pairingSecret, agentPubkey, and sessionId are required");
  }
  const params = new URLSearchParams({
    relay: relayUrl,
    token,
    secret: pairingSecret,
    agent_key: agentPubkey,
    session: sessionId,
  });
  if (hostname) {
    params.set("hostname", hostname);
  }
  return `termhop://pair?${params.toString()}`;
}

export function decodePairingLink(link) {
  let url;
  try {
    url = new URL(link);
  } catch (err) {
    throw new PairingLinkError(`not a valid URL: ${err.message}`);
  }

  if (url.protocol !== "termhop:" || url.hostname !== "pair") {
    throw new PairingLinkError("not a termhop://pair link");
  }

  const relayUrl = url.searchParams.get("relay");
  const token = url.searchParams.get("token");
  const hostname = url.searchParams.get("hostname") ?? "";
  const pairingSecret = url.searchParams.get("secret");
  const agentPubkey = url.searchParams.get("agent_key");
  const sessionId = url.searchParams.get("session");

  if (!relayUrl || !token || !pairingSecret || !agentPubkey || !sessionId) {
    throw new PairingLinkError("pairing link missing authenticated pairing fields");
  }

  let relay;
  try {
    relay = new URL(relayUrl);
  } catch (err) {
    throw new PairingLinkError(`invalid relay URL: ${err.message}`);
  }
  const loopback = relay.hostname === "localhost" || relay.hostname === "127.0.0.1" || relay.hostname === "[::1]";
  if (relay.protocol !== "wss:" && !(relay.protocol === "ws:" && loopback)) {
    throw new PairingLinkError("relay must use wss:// (ws:// is allowed only on loopback)");
  }

  return { relayUrl, token, pairingSecret, agentPubkey, sessionId, hostname };
}
