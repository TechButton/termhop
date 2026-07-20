# termhop

termhop gives you an end-to-end encrypted terminal in a phone or desktop browser. The agent runs on your computer, the relay moves encrypted messages between devices, and terminal contents stay unreadable to the relay.

## Try the disposable demo

Visit **[app.42oclock.com](https://app.42oclock.com/demo)** and choose **Start disposable demo**. It boots an isolated Linux environment and connects the browser automatically—there is nothing to install or pair. The 10-minute allowlist includes Snake, 2048, original ANSI space and Matrix animations, a relay showcase, and restricted Codex and Claude launchers. The environment is destroyed when you log out or time expires.

## What you need

For the hosted demo, only a current browser is required.

To connect your own computer, you need:

- Python 3.11 or newer and Git on the computer running the agent
- Linux, macOS, or Windows 10/11
- A modern browser with JavaScript enabled
- A `wss://` relay URL reachable by both devices

To run your own relay, Docker Compose is recommended, with a TLS reverse proxy
or load balancer. A hardened native Linux/systemd installation is also
supported. See [relay deployment and VPS sizing](docs/RELAY_DEPLOYMENT.md).
The relay listens on `127.0.0.1:8080`; expose it through HTTPS/WSS rather than
publishing that port directly to the internet.

## Install the agent

The browser client does not need to be installed: open
[client.42oclock.com](https://client.42oclock.com). Install the agent only on
the Linux, macOS, or Windows computer whose terminal you want to reach.

Before installing, verify `python`/`python3` is version 3.11 or newer and that
`git` is available. See the [complete OS installation guide](docs/INSTALL.md)
for prerequisites, persistent startup, verification, updating, troubleshooting,
and removal.

Linux:

```sh
curl -fsSL https://raw.githubusercontent.com/TechButton/termhop/main/agent/linux/install.sh | sh
```

macOS:

```sh
curl -fsSL https://raw.githubusercontent.com/TechButton/termhop/main/agent/macos/install.sh | sh
```

Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/TechButton/termhop/main/agent/windows/install.ps1 | iex
```

The Windows installer is per-user and does not require an Administrator
PowerShell window.

Pair the installed agent with your relay:

```sh
termhop-agent pair --relay wss://relay.example.com
```

The command prints an authenticated pairing link and a terminal QR code. Open
[client.42oclock.com](https://client.42oclock.com), choose **Pair your relay**,
then scan the terminal QR code or select **Paste URL**. Pairing secrets are short-lived
and are sent out of band from the relay connection.

## Run a relay

```sh
git clone https://github.com/TechButton/termhop.git
cd termhop
cp .env.example .env
docker compose up -d --build
curl http://127.0.0.1:8080/healthz
```

Before starting, set `DOMAIN` in `.env` to the public relay hostname. Configure
your reverse proxy to terminate TLS and proxy WebSocket traffic to
`127.0.0.1:8080`. Redis holds transient routing state only and persistence is
disabled intentionally.

## Repository layout

- `relay-server/` — FastAPI WebSocket relay and routing-token service
- `agent/common/` — shared protocol, encryption, pairing, and session code
- `agent/linux/` — Linux PTY agent and systemd user service
- `agent/macos/` — macOS PTY agent and launchd configuration
- `agent/windows/` — Windows ConPTY agent and per-user Startup launcher

## Security and scope

Protocol v2 encrypts terminal data between the browser client and agent. The relay receives routing metadata and ciphertext, not terminal plaintext. Authenticated pairing pins the agent's public key before a terminal session starts.

Read [SECURITY.md](SECURITY.md), the [code reference](docs/CODE_REFERENCE.md),
[persistent session lifecycle](docs/SESSION_LIFECYCLE.md), the
[release checklist](docs/RELEASE_CHECKLIST.md), and the
[security audit](docs/SECURITY_AUDIT_2026-07-20.md) before production
deployment.

The relay server and agents are licensed under [AGPL-3.0](LICENSE). The hosted account service and browser client are operated separately and are not part of this repository.
