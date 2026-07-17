# relay-server

FastAPI + WebSockets relay implementing the pairing and routing message
types from `../PROTOCOL.md`. Status: v1 built — pairing handshake routing,
session-control routing, terminal-data routing, port-forward routing,
per-IP/per-token rate limiting, and payload-blind logging are all
implemented and tested. Not yet exercised against a real agent or client
(neither exists yet — see `../PROJECT_PLAN.md` build order); tested against
a fake-peer WebSocket harness that stands in for both.

## Scope

- Never decrypts `pty_data`/`pty_input`/`port_forward_data` payloads — see
  `../SECURITY.md`. The router (`relay/router.py`) forwards every routable
  envelope verbatim by `session_id`, without ever inspecting `payload`
  contents.
- Redis (via `relay/pairing.py`) holds pairing-token state and short-lived
  session records; the live WebSocket objects themselves are only ever
  in-process (`relay/session_registry.py`) — a relay restart requires
  re-pairing, by design (no cross-restart session resume in v1).
- Two small protocol clarifications beyond the original `PROTOCOL.md` draft
  were needed to make this concrete — see that doc's updated Pairing section:
  the agent generates both the pairing token and the `session_id`, and two
  new message types (`pair_init_ack`, `error`) were added to the vocabulary.

## Running locally

```bash
cd relay-server
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest                      # full suite, uses an embedded redislite instance
ruff check relay/ tests/
mypy relay/
```

Dev/test dependencies use `redislite` (an embedded real `redis-server`
binary) rather than `fakeredis`, specifically so the Lua-script-based
single-use-token and rate-limit logic is exercised against real Redis
semantics, not a mock with known `EVAL` gaps.

Production/deployment uses a real `redis:7-alpine` container — see the root
`docker-compose.yml` and `../DEPLOYMENT.md`. Verified: `docker compose build
relay && docker compose up -d` brings up both containers cleanly (Redis
healthcheck gates relay startup), `/healthz` responds, and a full
pair_init→pair_challenge→pair_complete→pty_data→session_close round trip via
a raw `websockets` client against the containerized instance works, with a
canary marker confirmed absent from both `docker compose logs relay` and
`redis-cli KEYS *`/values afterward.

## Before writing more code here

Read `../PROTOCOL.md` in full and `../SECURITY.md`'s "Pairing Model" and
"Relay Server Security" sections — the encryption handshake is
non-negotiable from the first commit, not a later addition.
