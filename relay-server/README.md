# relay-server

Not yet implemented — this is the next component per `PROJECT_PLAN.md`'s
build order (step 1).

## Scope

- FastAPI + `websockets`, brokers agent<->client connections.
- Implements the pairing (`pair_init`/`pair_request`/`pair_challenge`/
  `pair_complete`) and routing message types from `../PROTOCOL.md`.
- Never decrypts `pty_data`/`pty_input`/`port_forward_data` payloads —
  see `../SECURITY.md` for the exact boundary.
- Redis for pairing-token state and (optional) session-resume persistence.

## Before writing code here

Read `../PROTOCOL.md` in full and `../SECURITY.md`'s "Pairing Model" and
"Relay Server Security" sections — the encryption handshake is
non-negotiable from the first commit, not a later addition.
