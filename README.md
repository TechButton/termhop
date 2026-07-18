# termhop

Self-hosted, open-source remote terminal control. Run Claude Code, Codex, PowerShell,
bash, or any CLI on a Linux, macOS, or Windows machine, and control it live from
your phone or a browser — through a relay you own, with end-to-end encryption
the relay can never see through, and **no inbound ports opened anywhere.**

Inspired by the feature set of deverywhere.io; built as an independent,
self-hosted alternative under AGPL-3.0.

## How it works

```
  PC Agent (Linux/macOS/Windows)          Relay (self-hosted)          Phone/Browser Client
  ─────────────────────────────           ──────────────────           ─────────────────────
  Outbound connection only  ─────────▶   Brokers ciphertext   ◀──────  Outbound connection only
  Spawns real PTYs, streams               only. Never holds              QR/link pairing,
  encrypted I/O                            decryption keys.                xterm.js rendering
```

- The **agent** runs on the machine you want to control. It dials *out* to the relay — nothing listens for inbound connections on the PC.
- The **relay** is the only publicly reachable component. It brokers encrypted traffic between agent and client but cannot decrypt it.
- The **client** (mobile web app / Capacitor wrapper, or plain browser) dials *out* to the relay, pairs via QR/link, and renders the real terminal.

See [`PROJECT_PLAN.md`](./PROJECT_PLAN.md) for full architecture and build order,
and [`SECURITY.md`](./SECURITY.md) for the threat model and encryption design.

## Status

Protocol v2 pairing, the relay, cross-platform agent code, browser terminal,
saved-device reboot reconnection, tests, and CI are implemented locally. See
[`PROGRESS.md`](./PROGRESS.md) for the exact verified/deployed distinction.

## Repo Layout

```
termhop/
├── relay-server/      # FastAPI relay (brokers ciphertext, never decrypts)
├── agent/
│   ├── common/         # shared session/protocol logic
│   ├── linux/            # ptyprocess backend + systemd unit
│   ├── macos/          # ptyprocess backend (shared w/ linux) + launchd plist
│   └── windows/        # pywinpty backend + Windows service
├── client/                # Capacitor + web app (xterm.js)
├── PROJECT_PLAN.md
├── PROTOCOL.md
├── SECURITY.md
├── CONTRIBUTING.md
├── DEPLOYMENT.md
├── LICENSE
└── docker-compose.yml
```

## Quickstart

```bash
# 1. Stand up the relay (self-hosted, behind your own domain/tunnel)
git clone https://github.com/<you>/termhop
cd termhop/relay-server
docker compose up -d

# 2. Install the agent on the machine you want to control
curl -fsSL https://raw.githubusercontent.com/<you>/termhop/main/agent/linux/install.sh | sh
termhop-agent pair --relay wss://your-relay.example.com

# 3. Scan the QR code with the phone client, or open the web client and paste the pairing link
```

## License

- `relay-server/` and `agent/`: AGPL-3.0
- `client/`: MIT

See [`LICENSE`](./LICENSE) and the licensing section in [`PROJECT_PLAN.md`](./PROJECT_PLAN.md) for rationale.

## Contributing

See [`CONTRIBUTING.md`](./CONTRIBUTING.md) and the annotated module map in
[`CODE_GUIDE.md`](./CODE_GUIDE.md). Hosted accounts are optional; the boundary
is documented in [`HOSTED_SERVICE.md`](./HOSTED_SERVICE.md).

## Security

Found a vulnerability? Do not open a public issue — see the reporting process in [`SECURITY.md`](./SECURITY.md).
