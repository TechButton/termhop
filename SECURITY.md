# SECURITY.md — termhop

## Threat Model

`termhop` gives a phone remote control of a real terminal on a PC — this is
high-value access (arbitrary command execution, file read/write, credentials
in scrollback). The design goal is: **even a fully compromised or malicious
relay server cannot read or inject terminal traffic, and a stolen pairing
link/token has a short, bounded window of usefulness.**

### Assets to protect
- Terminal input/output (may contain source code, secrets, credentials, `.env` contents, tokens pasted into a CLI).
- Pairing credentials (QR code / pairing link).
- The PC agent's ability to execute arbitrary commands.

### Trust boundaries
- **Relay server** — untrusted for content, trusted only for availability/routing. Assume it could be compromised, subpoenaed, or logging more than intended.
- **Network path** (phone ↔ relay, relay ↔ PC) — assume hostile (public wifi, cellular, etc.).
- **PC agent host** — trusted (it's your machine); agent inherits the permissions of the user account running it.
- **Phone client** — trusted once paired; loss of the physical device or an unlocked session is the main risk here.

## Pairing Model

1. PC agent generates a **single-use pairing token** (short random ID, e.g. 128-bit) and an **ephemeral key pair** (X25519).
2. QR code / pairing link encodes: relay URL, pairing token, agent's ephemeral public key.
3. Token has a short TTL (default: 2 minutes) and is invalidated after first use or expiry — whichever comes first.
4. Phone client scans, connects to relay, presents the token. Relay forwards the *connection request only* — it does not generate or see any key material used for the actual encryption.
5. Phone and agent perform an **ECDH handshake** directly (relayed as opaque bytes) to derive a shared session key. All subsequent PTY traffic is encrypted with this key (e.g. XChaCha20-Poly1305 or AES-256-GCM) before it touches the relay.
6. Long-term pairing (so you don't re-scan every time) is done by persisting the derived long-term key pair per device, not by reusing the pairing token.

**Relay's view of traffic post-pairing:** opaque ciphertext, session ID, and byte-count/timing metadata needed for idle detection. It cannot decrypt terminal content even with full access to its own database and logs.

## Session Security

- Each PTY session gets its own session key derivation (or key ratcheting) — compromising one session's traffic should not expose others.
- Idle/permission-prompt detection happens **agent-side**, on the plaintext the agent already has locally, before encryption — the relay is not doing pattern matching on your terminal output.
- Resumable sessions: state needed for resume (session ID, encrypted last-N-lines buffer) should itself be encrypted at rest if stored server-side (e.g. in Redis), not just in transit.

## Agent Security

- The agent should run with the **minimum privilege needed** — document clearly that anyone running it as root/Administrator is extending phone-access to root/Administrator-level command execution.
- No default "skip permissions" / auto-accept mode shipped enabled — if you replicate deverywhere's "auto-accept" toggle, it should be opt-in per session, not a global default, and should be visually distinct in the client so it's obvious when it's on.
- Agent should bind only to localhost / the relay's outbound connection — it should not open an inbound listening port on the PC's network interface by default (avoids exposing a raw terminal to the LAN).
- Config files (relay URL, long-term keys) should never be committed to example configs; ship `.env.example` with placeholders only.

## Relay Server Security

- Rate-limit pairing attempts per IP and per token to prevent brute-forcing a short pairing token.
- Enforce TLS (wss://) on every hop as a baseline transport protection — but this is a floor, not the actual security boundary. The relay must never be able to decrypt session content even if TLS is terminated correctly and the relay operator is fully cooperative with an attacker. The **application-layer E2E encryption (ECDH-derived session keys) is mandatory and non-optional** — there is no "trusted relay" deployment mode.
- Don't log message payloads, even at debug level, in production builds — only metadata needed for operations (connection counts, error rates).
- Isolate relay from any other service on the same host/network if possible (least exposure if it's ever compromised).

## Known Limitations (be upfront about these in the repo)

- A compromised **PC agent host** or **unlocked phone** defeats this model — encryption protects the network/relay hop, not the endpoints.
- Terminal scrollback may contain secrets typed or displayed during a session; this tool doesn't redact or scan content — treat any paired session like local shell access, because that's what it is.
- Push notification content (e.g. "waiting for input") goes through whatever push provider is used (APNs/FCM if using Capacitor's native push) — keep notification bodies generic (no command text) to avoid leaking session content through the push provider.

## Reporting a Vulnerability

State your intended process here once public, e.g.:
- Report privately via [email/security contact], not a public GitHub issue.
- Target acknowledgment time and disclosure timeline (e.g. 90-day coordinated disclosure).
- Whether you'll credit reporters / run a security.txt.

## Before First Public Release Checklist

- [ ] Independent review of the ECDH handshake implementation (don't hand-roll crypto primitives — use a vetted library, e.g. `libsodium`/`pynacl` or `cryptography`).
- [ ] Confirm relay cannot decrypt traffic even with DB + log access (test by auditing what's actually stored).
- [ ] Pairing token brute-force testing (confirm rate limits hold).
- [ ] Default config ships with auto-accept/skip-permissions OFF.
- [ ] `.env.example` and docs contain no real hostnames/tokens from your own deployment.
