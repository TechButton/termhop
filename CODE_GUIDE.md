# Code guide

This guide is the map for readers approaching the open-source repository for
the first time. Source files also contain module comments, function docstrings,
and inline rationale around security-sensitive or non-obvious branches. We do
not comment punctuation or restate assignments: comments that duplicate syntax
go stale and make audited code harder to read.

## Request path

1. `agent/<platform>/main.py` selects the operating-system PTY backend and
   delegates CLI behavior to `agent/common/cli.py`.
2. `agent/common/relay_client.py` performs initial pairing or saved-device
   reconnection and encrypts/decrypts wire payloads using `crypto.py`.
3. `relay-server/relay/ws_handlers.py` accepts role-specific WebSockets and
   validates envelope size, version, and sequence ordering.
4. `relay-server/relay/router.py` binds each socket to one session, validates
   public handshake fields, and forwards opaque encrypted payloads.
5. `client/src/lib/relayClient.js` mirrors the agent state machine. React
   screens call it but do not implement cryptography themselves.
6. `client/src/screens/TerminalScreen.jsx` connects xterm.js to the already
   authenticated `RelayClient`; it never opens a second session socket.

## Durable reconnection

- `agent/common/config.py` stores the relay URL, random device ID, and durable
  256-bit device secret in the platform config directory. POSIX permissions
  are forced to `0600`.
- `client/src/lib/savedDevices.js` stores the matching credential in browser
  site data. It is never uploaded to the hosted account service or relay.
- Hosted-mode records are tagged with the logged-in account and hidden after
  logout; self-hosted records remain available without any account.
- The first session delivers that credential as encrypted
  `device_credential`; it is distinct from the expiring pairing-link secret.
- `resume_init`/`resume_request` locate the two online endpoints. A fresh
  X25519 exchange plus role-bound proofs derived with the durable secret then
  authenticates both endpoints and creates new directional traffic keys.
- A reboot kills every OS process and PTY. Reconnection therefore starts a new
  shell and marks the old session interrupted; it does not pretend the old
  process survived.

## Optional hosted accounts

The public client has no account dependency by default. Setting
`VITE_CONTROL_PLANE_URL` enables an OAuth-style, one-time handoff to an
operator-provided control plane. The Frequency 42 hosted implementation lives
in a separate private repository and is not imported or required here.

## Tests as executable documentation

- `relay-server/tests/test_device_resume.py` shows every relay-visible resume
  envelope in order.
- `agent/tests/test_relay_client_handshake.py` proves Python endpoint behavior
  against a real local relay.
- `client/src/lib/relayClient.test.js` shows browser pairing, proofs,
  encryption, buffering, replay rejection, and reconnection.
- `client/e2e/pairing.spec.js` boots an isolated real relay and Linux agent,
  pairs through the browser, and executes a real shell command.
