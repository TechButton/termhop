# DEPLOYMENT.md — Self-Hosting termhop

This covers standing up your own relay and installing agents. Nothing here
requires a third-party hosted service — that's the point.

## 1. Relay Server

### Requirements
- A host with a public DNS name and the ability to get a TLS cert (Let's Encrypt via Nginx, or behind an existing tunnel like Pangolin/Cloudflare Tunnel).
- Docker + Docker Compose (recommended), or Python 3.11+ if running bare.

### Option A — Docker Compose (recommended)

```bash
git clone https://github.com/TechButton/termhop
cd termhop/relay-server
cp .env.example .env
# edit .env: set DOMAIN, RELAY_PORT, REDIS settings if using session persistence
docker compose up -d
```

Front it with Nginx + Let's Encrypt (same pattern as any other self-hosted
service — see your own `vault.42oclock.com`-style setup for a template):

```nginx
server {
    listen 443 ssl;
    server_name relay.yourdomain.com;
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### Option B — Behind an existing WireGuard/Pangolin tunnel

If you already have a tunnel exposing internal services publicly, point it at
the relay's local port instead of standing up a new Nginx vhost. No change to
the relay itself — it doesn't care how traffic reaches it, only that it
arrives over TLS.

### Option C — Bare Python (no Docker)

```bash
cd relay-server
pip install -r requirements.txt
uvicorn relay.main:app --host 0.0.0.0 --port 8080
```

Not recommended for production — Docker Compose also brings up Redis (used
for pairing-token state and optional session-resume persistence).

## 2. Agent Installation

The agent needs outbound network access to your relay's `wss://` endpoint.
**No inbound firewall rule is needed on the agent machine.**

### Linux

```bash
curl -fsSL https://raw.githubusercontent.com/TechButton/termhop/main/agent/linux/install.sh | sh
termhop-agent pair --relay wss://relay.yourdomain.com
```

Installs as a systemd user service (`~/.config/systemd/user/termhop-agent.service`)
so it survives reboots without running as root. After pairing once (so a
relay URL is persisted), enable it and enable linger — **a systemd *user*
unit does not run at boot without an active login session unless linger is
enabled for that user**, which is easy to miss:

```bash
systemctl --user enable --now termhop-agent
loginctl enable-linger $USER
```

### macOS

```bash
curl -fsSL https://raw.githubusercontent.com/TechButton/termhop/main/agent/macos/install.sh | sh
termhop-agent pair --relay wss://relay.yourdomain.com
```

Installs as a `launchd` agent (`~/Library/LaunchAgents/io.termhop.agent.plist`),
runs under your user account.

### Windows

```powershell
irm https://raw.githubusercontent.com/TechButton/termhop/main/agent/windows/install.ps1 | iex
termhop-agent.exe pair --relay wss://relay.yourdomain.com
```

Installs as a Windows service (or scheduled task at logon, if you'd rather
avoid running under the Service account context — this affects which user
context spawned terminals run under, worth choosing deliberately).

## 3. Pairing a Client

1. Run `termhop-agent pair` on the PC — this prints a QR code and a pairing link, both short-lived (default 2 minutes).
2. Open the phone app or web client, scan the QR or paste the link.
3. Client and agent perform the ECDH handshake through the relay (relay never sees the derived key).
4. Once paired, the client persists a long-term key for that agent so future connects don't require re-scanning.

## 4. Verifying Your Deployment

- Confirm `wss://` (not `ws://`) is what the client actually connects to — check browser devtools network tab or agent logs.
- Confirm the relay's port is **not** reachable directly from outside the host (e.g. `curl http://<server-ip>:8080/healthz` from another machine should fail/time out) — only the reverse proxy's 80/443 should be reachable. `docker-compose.yml` publishes the relay port bound to `127.0.0.1` for exactly this reason; if you've customized the compose file, don't drop that binding. Found live on a real deployment during this project's own beta rollout — nginx was correctly terminating TLS, but the relay's plain port was *also* open to the world in parallel, letting anyone connect over unencrypted `ws://` and bypass TLS entirely.
- Confirm the relay's logs do **not** contain PTY content — see the checklist in `SECURITY.md` section "Before First Public Release."
- Test idle-alert delivery end-to-end before relying on it.

## 5. Updating

```bash
cd termhop
git pull
docker compose pull && docker compose up -d   # relay
termhop-agent update                            # agent, each platform
```

Pin versions in production if you're not ready to track `main` — releases will
be tagged once the project reaches a stable v1.
# Optional hosted-account client build

The open-source client has no hosted dependency by default. Operators who run
an account/control-plane site opt in at build time:

```bash
cd client
VITE_CONTROL_PLANE_URL=https://accounts.example.com npm run build
```

Frequency 42's hosted build uses `https://app.42oclock.com`; a self-hosted
build leaves the variable empty and exposes direct relay pairing only. This is
a Vite build-time value, so changing it requires rebuilding static assets but
does not require changing the relay or agent.
