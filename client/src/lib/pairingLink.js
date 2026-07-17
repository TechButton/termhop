// termhop client — encode/decode the termhop://pair pairing link/QR
// payload. Format: termhop://pair?relay=<url-encoded ws(s)://...>&token=<token>&hostname=<url-encoded hostname>
//
// The client only needs {relayUrl, token} before sending pair_request — the
// agent's pubkey and hostname both arrive for the first time in
// pair_challenge, so hostname here is purely for nicer pre-handshake UI
// copy (GUI_SPEC.md's "This device will be able to run commands on
// <agent hostname>"), not a protocol requirement. session_id is
// deliberately omitted — the client never needs it before pair_challenge
// returns it.
//
// Plain-text query-string over a base64 JSON blob: the token is already
// URL-safe (relay's format is ^[A-Za-z0-9_-]+$), only relay/hostname need
// percent-encoding, and this stays human-readable when pasted.

export class PairingLinkError extends Error {}

export function encodePairingLink({ relayUrl, token, hostname = "" }) {
  if (!relayUrl || !token) {
    throw new PairingLinkError("relayUrl and token are required");
  }
  const params = new URLSearchParams({ relay: relayUrl, token });
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

  if (!relayUrl || !token) {
    throw new PairingLinkError("pairing link missing relay or token");
  }

  return { relayUrl, token, hostname };
}
