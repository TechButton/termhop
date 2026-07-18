# Project Plan — Remote Terminal Access Tool (working name: "termhop")

> Rename freely — this doc uses `termhop` as a placeholder wherever a project name is needed.

## 1. Goal

A self-hostable, open-source system that lets you control real terminal sessions
(Claude Code, Codex, PowerShell, cmd.exe, bash, any CLI) running on a PC from a
phone, over a relay you own. Inspired by deverywhere.io's feature set, built as
an independent, self-hosted alternative.

## 2. Components

```
┌─────────────┐      wss (encrypted)      ┌─────────────┐      wss (encrypted)      ┌─────────────┐
│  PC Agent    │ ───────────────────────▶ │ Relay Server │ ◀─────────────────────── │ Phone Client │
│ (Python)     │ ◀─────────────────────── │ (FastAPI/WS) │ ───────────────────────▶ │ (Capacitor)  │
└─────────────┘                            └─────────────┘                            └─────────────┘
     │
     ├─ Linux: os.forkpty / ptyprocess
     └─ Windows: pywinpty (ConPTY)
```

### 2.1 Relay Server
- **Stack:** FastAPI + `websockets`, Redis for pairing-token/session state (optional at v1, useful once you add session resume across relay restarts).
- **Responsibilities:**
  - Register and atomically consume agent-generated routing tokens for QR/link pairing; never receive the separate out-of-band pairing secret.
  - Broker two WebSocket connections per current v2 session: agent↔relay and client↔relay, with each socket bound to one session and role.
  - **Never decrypt payloads** — see SECURITY.md. Relay only sees ciphertext + minimal routing metadata (session ID, timestamps, byte counts for idle detection).
  - Rate-limit connection attempts and pairing token use.
- **Deployment:** Docker container behind Nginx + Let's Encrypt, same pattern as your `vault.42oclock.com` setup. Can sit behind your Pangolin tunnel or a small public VPS.

### 2.2 PC Agent
- **Stack:** Python, single codebase with OS-specific PTY backend.
  - Linux: `ptyprocess` (wraps `os.forkpty`).
  - macOS: same `ptyprocess`/`forkpty` approach as Linux (POSIX PTY) — packaging differs (notarized `.app` or Homebrew formula, `launchd` service instead of systemd).
  - Windows: `pywinpty` (wraps ConPTY) — required for real color/cursor support in cmd.exe/PowerShell/claude.exe.
- **No inbound ports, on any platform.** The agent always initiates an outbound connection to the relay and holds it open. Nothing needs to be opened on the PC's firewall or router — this holds for Linux, macOS, and Windows identically.
- **Responsibilities:**
  - Spawn and track PTY sessions (PID, cwd, launch command, last-output timestamp).
  - Stream PTY output to relay; accept keystrokes/resize events from relay.
  - Detect idle state (no output for N seconds) and specific prompt patterns (e.g. "Make this edit? Y/n") to trigger push notifications.
  - Optional: local port-forward listener for the port-forwarding feature — this tunnels a *dev server's* port out through the same outbound relay connection; it does not require opening an inbound port either.
  - Runs as a background service: systemd unit (Linux), launchd agent (macOS), Windows service or scheduled task (Windows).

### 2.3 Phone Client
- **Stack:** Web app (xterm.js for terminal rendering, WebSocket transport) wrapped in Capacitor for push notifications and home-screen install.
- **Responsibilities:**
  - QR/link pairing flow (scan → ECDH handshake → paired).
  - Render live terminal(s), session list (live + resumable), virtual key row (Ctrl/Esc/Tab/arrows).
  - Receive and display idle/permission-prompt push notifications.
  - Port-forward UI: list forwarded ports, open in in-app browser view.

### 2.4 Shared Protocol
- A short spec doc (`PROTOCOL.md`) defining the WebSocket message format (JSON envelope: `type`, `session_id`, `seq`, `payload`) so third parties could write alternative agents or clients without reading your code. Keeps the ecosystem open even if your reference implementation isn't the only one.
- Protocol v2 authenticates the QR/link handshake against a malicious relay, derives directional traffic keys, binds encrypted metadata as AEAD associated data, and rejects replayed sequences.
- Durable device routing is now split from fresh attachment/session keys. The
  remaining multi-PTY work must preserve that separation (see `PROTOCOL.md`).

## 3. Build Order

> **Non-negotiable from day one:** every hop is encrypted end-to-end (agent↔client, relay blind to content), and the project is open source from the first commit. Neither is a "later" step — see below.

1. **Relay server** — pairing + message brokering. Ships with the encryption handshake (ECDH at pairing time) built in from the first working version, not bolted on afterward. Relay only ever sees ciphertext + routing metadata.
2. **Linux agent** — spawn one PTY, stream encrypted traffic to relay, confirm round-trip with a raw test client. No plaintext-transport milestone — encrypted is the only mode that exists.
3. **Phone web client (PWA, pre-Capacitor)** — xterm.js rendering, virtual keys, session list, performs its half of the ECDH handshake. Test in mobile browser.
4. **Windows agent** — pywinpty backend, same encrypted protocol.
5. **macOS agent** — reuses the Linux/POSIX PTY code path almost as-is; work here is packaging (notarized `.app` / Homebrew) and the launchd service definition, not new PTY logic.
6. **Idle detection + push notifications** — agent-side pattern matching on local plaintext (pre-encryption), relay delivery, Capacitor push integration.
7. **Port forwarding** — local listener on agent, tunnel through relay, client-side access. Forwarded traffic is encrypted the same way as PTY traffic.
8. **Capacitor packaging** — wrap the working PWA, add native push, publish/self-distribute.
9. **Open-source packaging** — license file, `SECURITY.md`, `PROTOCOL.md`, config templates, CONTRIBUTING.md, strip env-specific values. This isn't a final step tacked on — repo is public and under license from the start; this step is polishing docs/onboarding for outside contributors, not "deciding to open it up."

## 4. Repo Structure

```
termhop/
├── relay-server/        # FastAPI relay
├── agent/
│   ├── common/           # shared session/protocol logic
│   ├── linux/             # ptyprocess backend + systemd unit
│   ├── macos/           # ptyprocess backend (shared w/ linux) + launchd plist + notarization
│   └── windows/          # pywinpty backend + Windows service
├── client/                  # Capacitor + web app (xterm.js)
├── PROTOCOL.md
├── SECURITY.md
├── CONTRIBUTING.md
├── LICENSE
└── docker-compose.yml   # relay + optional Redis for local/self-hosted spin-up
```

## 5. Licensing — Decided

Open source is a requirement, not an option to revisit later. Repo goes public
under license from the first commit.

**AGPL-3.0** for `relay-server/` and `agent/` — keeps it open while ensuring anyone
running a modified version as a network service (e.g. a competing hosted relay)
must release their changes. This leaves the door open if Frequency 42 LLC later
offers a hosted-relay tier itself.

`client/` can optionally be MIT if you want it easy for others to embed in their
own frontends — client code has less "hosted service" risk than the relay.

## 6. Naming / Trademark Note

Pick a name distinct from "deverywhere" before publishing, since this project
will publicly reference and functionally compete with it. A quick trademark/
domain check before settling on a final name avoids friction later.

## 7. Open Items to Decide Before Public Release

- [ ] Final project name + domain
- [ ] Where the reference relay instance (if you host a public demo) will live
- [ ] Whether session-resume state persists in Redis or just in-memory (affects relay restart behavior)
- [ ] Push notification provider (self-hosted ntfy.sh vs. Capacitor's native push vs. web push)
- [x] CI setup (lint/test/build on PR, including macOS/Windows PTY jobs)
