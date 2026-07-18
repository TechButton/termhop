# PROGRESS.md — what's built so far

Status snapshot as of 2026-07-17. See `PROJECT_PLAN.md` for the intended
build order this follows, and each subdirectory's own README for
component-level detail. This file is the single "what's actually done"
record — update it at the end of each build phase rather than
reconstructing it from git log later.

## Live deployment (beta box, 107.172.133.223)

- `termhop.42oclock.com` — relay-server, real TLS via Let's Encrypt/nginx,
  Docker Compose `beta` profile (`relay-beta` + `redis-beta`), relay port
  bound to `127.0.0.1` only (nginx terminates TLS, proxies to it).
- `app.42oclock.com` — termhop-control-plane (separate private repo):
  marketing page, public signup (not promoted), login, email verification
  and password reset via Google Workspace SMTP, dashboard, per-tenant
  provisioning of an isolated relay+Redis Docker Compose stack per
  account.
- `client.42oclock.com` — client PWA static build (Vite), served by nginx
  from `/var/www/termhop-client`.
- Old "RallyText alpha" app that previously ran on this box: code backed
  up to `~/backups/` on the box, pm2 process stopped, `mcic` user and its
  nginx conf removed. Box itself was repurposed, not wiped.

The hosted protocol-v2 cutover was deployed on 2026-07-17 from public revision
`0dc7ab3` and private control-plane revision `014e21a`. The public relay health
endpoint reports protocol 2 and release `0dc7ab3`; nginx serves the hosted
client from a versioned static directory. Existing installed pre-v2 agents
still require upgrade and re-pairing.

## Protocol-v2/security pass — built, verified, hosted cutover deployed

- Authenticated pairing URI now carries a relay routing token, a separate
  256-bit secret that never enters a relay envelope, pinned agent public key,
  and pinned session ID. Both endpoints exchange transcript/role-bound proofs.
- HKDF derives separate agent→client, client→agent, and proof keys. Encrypted
  messages bind direction/type/session/sequence as XChaCha20-Poly1305 AAD;
  endpoints reject replayed encrypted sequences.
- Relay hashes raw tokens in both pairing and rate-limit Redis keys, binds each
  socket to one role/session, rejects duplicate attachments, cross-session
  routing, and non-monotonic connection sequences.
- Browser client buffers handshake/initial PTY messages that arrive before a
  waiter or terminal mount. xterm dimensions now produce `session_resize`.
- Shared app shell fills the dynamic viewport at phone and desktop sizes;
  terminal code is lazy-loaded so xterm.js is not in the initial pairing bundle.
- Responsive client landing supports an optional hosted-login handoff while
  direct self-hosted pairing stays enabled by default. The sibling hosted
  control-plane now has a redesigned homepage, dashboard-to-client link,
  single-use handoff, origin-restricted exchange, and revocable client token.
- Initial pairing delivers a separate durable device credential only after
  mutual authentication and inside E2E encryption. After an agent/PC reboot,
  the browser negotiates fresh keys and retries reconnection automatically;
  the destroyed PTY is marked interrupted and a replacement shell starts.
- Shared agent CLI removes three duplicated platform flows; Linux honors
  `XDG_CONFIG_HOME`. GitHub Actions CI covers relay, Linux agent, client, and
  platform PTY tests on macOS/Windows.
- Local verification: relay 37 passed; agent 41 passed + 5 platform skips;
  client 39 unit + 2 browser E2E passed; hosted control-plane 31 tests passed,
  including all 3 Docker tenant-isolation tests; Ruff and mypy clean;
  production client build succeeds.

## relay-server/ — protocol-v2 beta deployed

FastAPI + Redis. Envelope validation, pairing (atomic single-use tokens,
SHA-256-hashed at rest, Lua-script CAS consumption in Redis), session
registry, WebSocket routing, rate limiting, structured logging. Payload
fields (`pty_data`/`pty_input`/`port_forward_data`) are never inspected —
  relay is E2E-blind by design. 37 tests, mypy/ruff clean. Dockerized.

## agent/ — done (Linux reference + macOS/Windows built, unverified on real HW)

- `agent/common/` — shared crypto (X25519 + HKDF-SHA256 + XChaCha20-Poly1305,
  proven byte-identical to the client's JS implementation via a pinned
  cross-language test vector), envelope handling, pairing state machine,
  relay WebSocket client, session pump, platform-branching config paths
  (Linux XDG / macOS `~/Library/Application Support` / Windows `%APPDATA%`),
  shared pairing-URI builder (`pairing_link.py`).
- `agent/linux/` — reference implementation. `ptyprocess`/`forkpty`,
  systemd `--user` unit, `install.sh`. Fully tested including a real
  end-to-end PTY test.
- `agent/macos/` — near-verbatim port of the Linux PTY backend (same
  `ptyprocess`/`forkpty` POSIX path), launchd per-user agent
  (`termhop-agent.plist`, modern `bootstrap`/`bootout` API), `install.sh`.
  PTY backend genuinely tested here (POSIX, same as Linux) — launchd
  lifecycle itself is NOT verified on real macOS hardware yet.
- `agent/windows/` — `pywinpty`/ConPTY backend, PowerShell installer
  (`install.ps1`, no compiled `.exe`), Scheduled-Task-at-logon
  (`-RunLevel Limited`, not a real Windows Service — avoids the
  `pywin32`/service-account privilege model). PTY backend tests are
  skip-guarded (`sys.platform != "win32"`) — written and reviewed but
  **not executed on real Windows**. Documented gaps needing real hardware:
  whether `read()` raises `EOFError` or returns empty on exit, whether
  `write()` needs `str` or `bytes`, whether `pywinpty` installs cleanly,
  whether the scheduled task actually registers/fires/restarts.
- Self-hosting a relay from any platform already works via the existing
  `--relay <url>` CLI flag — no additional work needed.
- 46 tests total (41 passed + 5 skipped-on-Linux-by-design for Windows).
  ruff/mypy clean across the whole `agent/` tree. Committed
  (`4b256de`, "Build macOS and Windows agents").

## client/ — done, wired to the live relay, real bugs found and fixed

React PWA, screens matching `GUI_SPEC.md`. `useTerminalSession` wired to
a real `RelayClient` (WebSocket + the same E2E crypto as the agent).
xterm.js terminal with `FitAddon`, `copyOnSelect: true`. 37 unit tests plus
2 Playwright E2E tests (real relay/agent PTY and desktop viewport coverage).

Real bugs found via the user's own live testing on `client.42oclock.com`
and fixed:
- Dark-theme background not covering the full viewport (`App.jsx` root
  div needed explicit `background`/`color`, not just CSS custom
  properties that ancestors outside its scope don't inherit).
- White-on-white virtual key buttons in the compact-sheet permission UI.
- Garbled/repeated-character row at the top of every session — root
  cause was a missing `import '@xterm/xterm/css/xterm.css'`, not a data
  or timing bug (several wrong theories — sizing race, StrictMode
  double-mount, font loading — investigated and disproved first with
  direct evidence before finding the real cause).

## termhop-control-plane/ (separate private repo) — done

Flask app: `Account`/`Session`/`EmailToken`/`PasswordResetToken`/
`TenantRelay` models, argon2id passwords, server-side revocable sessions
(opaque token + DB row, not signed cookies — so password reset can kill
all existing sessions), atomic single-use tokens (same pattern as the
relay's pairing tokens), dual JSON/HTML routes, Google Workspace SMTP
email (credentials copied from `~/tools/crewlog`'s `.env.local`, never
printed to chat). Per-tenant isolation model: one full relay+Redis Docker
Compose stack per account, verified for real with actual Docker (two
provisioned tenant stacks, cross-tenant Redis unreachable at the network
level, cross-tenant pairing token rejected). Deployed live at
`app.42oclock.com`.

## Known gaps / explicitly deferred

- Single PTY session per agent — no multi-session, idle-detection, or
  port-forwarding yet (later PROJECT_PLAN.md build-order steps).
- No compiled Windows `.exe` — PowerShell "clone + venv" install only.
- Hosted login restores account and relay metadata on the same browser. Device
  credentials intentionally remain local and are not synced to a new browser;
  future sync must be client-side encrypted so the operator cannot recover
  terminal access.
