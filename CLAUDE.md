# CLAUDE.md — termhop

Orientation for Claude Code (or any coding agent) working in this repo.
Read this first, then the specific doc your task touches.

## What this is

Self-hosted, open-source remote terminal control: run Claude Code, Codex,
PowerShell, bash, or any CLI on a Linux/macOS/Windows machine, and control
it live from a phone or browser through a relay you own. End-to-end
encrypted; the relay never sees plaintext. No inbound ports on the agent,
on any platform.

## Non-negotiables (do not implement around these)

1. **End-to-end encryption is mandatory, not a mode.** There is no
   "trusted relay" deployment option. See `SECURITY.md`.
2. **Agents never open inbound listeners.** Outbound-only to the relay,
   on Linux, macOS, and Windows alike.
3. **No plaintext transport path, ever**, even for local dev/testing.
4. **`Skip permissions` / auto-accept defaults OFF**, always, no
   exceptions — see `CONTRIBUTING.md` ground rules and
   `client/src/screens/NewSessionScreen.jsx` for how this is enforced
   in the UI.
5. **No hand-rolled crypto.** Use vetted libraries (`pynacl`/`libsodium`,
   `cryptography`) for the relay/agent; nothing custom without explicit
   sign-off.

Full rationale for all of these: `SECURITY.md`.

## Repo map

| Path | Status | What it is |
|---|---|---|
| `README.md` | done | Project overview, architecture diagram, quickstart |
| `PROJECT_PLAN.md` | done | Architecture, build order, licensing |
| `PROTOCOL.md` | done | Wire message format (agent<->relay<->client) |
| `SECURITY.md` | done | Threat model, pairing/encryption design |
| `CONTRIBUTING.md` | done | Ground rules, PR expectations |
| `DEPLOYMENT.md` | done | Self-hosting steps (relay + each agent platform) |
| `GUI_SPEC.md` | done | Screen-by-screen client spec |
| `TESTING.md` | stub | Fill in as components land |
| `LICENSE` / `client/LICENSE` | done | AGPL-3.0 (relay/agent), MIT (client) |
| `client/` | **scaffolded, not wired up** | React screens matching the design handoff. See `client/README.md` for exactly what's real vs. stubbed. |
| `relay-server/` | **not started** | See `relay-server/README.md` for scope |
| `agent/common/`, `agent/linux/`, `agent/macos/`, `agent/windows/` | **not started** | See each dir's README |

## Suggested build order

Per `PROJECT_PLAN.md` section 3: **relay server → Linux agent → wire
`client/` to a real relay → Windows agent → macOS agent → idle
notifications → port forwarding → Capacitor packaging.**

Encryption is not a separate step in this order — every stage above ships
encrypted from its first working version.

## Client specifics worth knowing before touching `client/`

- Accent color is locked to `#cc6a2e` (`client/src/styles/tokens.css`) —
  don't change it without asking; it was a deliberate pick from three
  options in the design handoff.
- Terminal screen's permission-prompt UI defaults to the **compact-sheet**
  variant (bottom sheet) — this was chosen over two alternatives the
  design handoff also included. See `client/README.md`.
- `client/src/screens/TerminalScreen.jsx` has a `useTerminalSession` stub
  showing exactly where xterm.js + encrypted pty_data/pty_input wiring
  goes — that's the natural next task once `relay-server/` and
  `agent/linux/` exist enough to test against.

## Design source

The original Claude Design handoff (prototype HTML/CSS, `.dc.html`
source, design-system tokens) is not included in this repo — `client/`
is the real, hand-translated implementation of it. If you need to check
something against the original mockup, ask the user; it's not checked in
here on purpose (prototype markup, not production code — see
`client/README.md` for why).
