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

1. The PC agent generates a **single-use routing token**, a separate 256-bit **pairing secret**, an ephemeral X25519 key pair, and a session ID.
2. The QR code / pairing link carries the relay URL plus all four pairing values. The secret, pinned agent key, and pinned session ID arrive out of band rather than through the relay WebSocket.
3. The routing token has a short TTL (default: 2 minutes) and is invalidated after first use or expiry. The relay stores only `SHA-256(token)` in Redis keys.
4. The client presents the routing token, its ephemeral key, and a proof derived from ECDH plus the out-of-band secret. The secret itself is never sent to the relay.
5. The agent verifies the client proof and returns a role-bound proof of its own. The client also requires the relayed agent key and session ID to match the pinned pairing-link values.
6. HKDF derives independent agent→client, client→agent, and proof keys. XChaCha20-Poly1305 authenticates message direction, type, session ID, and sequence as associated data.
7. After successful pairing, the agent transfers a separate random device ID
   and 256-bit device secret inside the authenticated encrypted channel; the
   pairing link does not contain this durable credential. Reconnection uses fresh ephemeral X25519 keys and
   role-bound proofs; it does not reuse the one-time routing token or old
   traffic keys.

**Relay's view of traffic post-pairing:** opaque ciphertext, session ID, and byte-count/timing metadata needed for idle detection. It cannot decrypt terminal content even with full access to its own database and logs.

## Session Security

- Each PTY session gets fresh ephemeral keys, pairing secret, and directional traffic keys — compromising one session's traffic should not expose others.
- Endpoints reject replayed/regressed encrypted sequence numbers. Direction-specific keys and authenticated metadata prevent ciphertext reflection, relabeling, or cross-session reuse.
- Idle/permission-prompt detection happens **agent-side**, on the plaintext the agent already has locally, before encryption — the relay is not doing pattern matching on your terminal output.
- Resumable sessions: state needed for resume (session ID, encrypted last-N-lines buffer) should itself be encrypted at rest if stored server-side (e.g. in Redis), not just in transit.

## Agent Security

- The agent should run with the **minimum privilege needed** — document clearly that anyone running it as root/Administrator is extending phone-access to root/Administrator-level command execution.
- No default "skip permissions" / auto-accept mode shipped enabled — if you replicate deverywhere's "auto-accept" toggle, it should be opt-in per session, not a global default, and should be visually distinct in the client so it's obvious when it's on.
- Agent should bind only to localhost / the relay's outbound connection — it should not open an inbound listening port on the PC's network interface by default (avoids exposing a raw terminal to the LAN).
- Config files (relay URL, long-term keys) should never be committed to example configs; ship `.env.example` with placeholders only.
- The POSIX agent config containing the durable device credential is forced to
  mode `0600`. Browser site data holding its peer credential is equivalent to
  a private key: XSS or an unlocked browser profile can use it, so deployments
  need a restrictive CSP and normal origin hygiene.

## Relay Server Security

- Rate-limit pairing attempts per IP and per token to prevent brute-forcing a short pairing token.
- Bind each live WebSocket to exactly one session ID and role; reject cross-session envelopes and duplicate live attachments.
- Enforce TLS (wss://) on every hop as a baseline transport protection — but this is a floor, not the actual security boundary. The relay must never be able to decrypt session content even if TLS is terminated correctly and the relay operator is fully cooperative with an attacker. The **application-layer E2E encryption (ECDH-derived session keys) is mandatory and non-optional** — there is no "trusted relay" deployment mode.
- Don't log message payloads, even at debug level, in production builds — only metadata needed for operations (connection counts, error rates).
- Isolate relay from any other service on the same host/network if possible (least exposure if it's ever compromised).

## Known Limitations (be upfront about these in the repo)

- A compromised **PC agent host** or **unlocked phone** defeats this model — encryption protects the network/relay hop, not the endpoints.
- Terminal scrollback may contain secrets typed or displayed during a session; this tool doesn't redact or scan content — treat any paired session like local shell access, because that's what it is.
- Push notification content (e.g. "waiting for input") goes through whatever push provider is used (APNs/FCM if using Capacitor's native push) — keep notification bodies generic (no command text) to avoid leaking session content through the push provider.
- Protocol v2 has durable device reconnection but still one PTY per agent. An
  operating-system reboot cannot preserve that PTY; reconnection creates a new
  shell. Multi-session separation and application-specific command resume are
  not implemented yet.
- Session/port-forward control metadata is not all encrypted yet. Port forwarding must not ship until its control messages are authenticated against malicious-relay injection.

## Reporting a Vulnerability

State your intended process here once public, e.g.:
- Report privately via [email/security contact], not a public GitHub issue.
- Target acknowledgment time and disclosure timeline (e.g. 90-day coordinated disclosure).
- Whether you'll credit reporters / run a security.txt.

## Before First Public Release Checklist

- [ ] Independent review of the ECDH handshake implementation (don't hand-roll crypto primitives — use a vetted library, e.g. `libsodium`/`pynacl` or `cryptography`).
- [x] Confirm relay cannot decrypt traffic with DB + log access; automated canary, cross-language proof, key-substitution, reflection/AAD, and replay tests cover the implemented boundary. Independent review is still required.
- [ ] Pairing token brute-force testing (confirm rate limits hold).
- [ ] Default config ships with auto-accept/skip-permissions OFF.
- [ ] `.env.example` and docs contain no real hostnames/tokens from your own deployment.
