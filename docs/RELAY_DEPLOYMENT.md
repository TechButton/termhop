# Relay deployment

Docker Compose is the recommended production installation. It pins Python
dependencies, runs the relay as a non-root user, keeps Redis off public ports,
and applies capability, process, memory, and filesystem restrictions. A native
Linux installation is supported for a dedicated host when the operator accepts
responsibility for Python, Redis, service, firewall, and upgrade lifecycle.

In both models, expose only TCP 443 through a TLS reverse proxy. The relay must
remain on loopback; never publish Redis. Set `CLIENT_ORIGINS` to the exact HTTPS
origins allowed to open browser WebSockets.

## Recommended: Docker Compose

```sh
git clone https://github.com/TechButton/termhop.git
cd termhop
cp .env.example .env
# Edit DOMAIN and CLIENT_ORIGINS before continuing.
docker compose config
docker compose up -d --build
curl http://127.0.0.1:8080/healthz
```

The Compose file binds the relay to `127.0.0.1`, drops Linux capabilities,
uses a read-only relay root filesystem, enables `no-new-privileges`, and caps
memory and process counts. Put Caddy, nginx, HAProxy, or a cloud load balancer
in front of port 8080 for a valid `wss://` endpoint.

Example Caddy site:

```caddyfile
relay.example.com {
    reverse_proxy 127.0.0.1:8080
}
```

## Native Linux/systemd option

Use a dedicated Debian/Ubuntu VPS. Commands below intentionally keep the
service account unable to log in and bind Uvicorn only to loopback.

```sh
sudo apt update
sudo apt install -y git python3 python3-venv redis-server
sudo useradd --system --home /opt/termhop --shell /usr/sbin/nologin termhop-relay
sudo git clone https://github.com/TechButton/termhop.git /opt/termhop
sudo python3 -m venv /opt/termhop/relay-server/.venv
sudo /opt/termhop/relay-server/.venv/bin/python -m pip install \
  -r /opt/termhop/relay-server/requirements.txt
sudo chown -R root:root /opt/termhop
sudo install -d -o root -g termhop-relay -m 0750 /etc/termhop
sudo install -o root -g termhop-relay -m 0640 /dev/null /etc/termhop/relay.env
sudo install -o root -g root -m 0644 \
  /opt/termhop/relay-server/termhop-relay.service \
  /etc/systemd/system/termhop-relay.service
```

Put this in `/etc/termhop/relay.env`:

```dotenv
DOMAIN=relay.example.com
REDIS_URL=redis://127.0.0.1:6379/0
PAIRING_TOKEN_TTL=120
PROTOCOL_VERSION=2
CLIENT_ORIGINS=https://your-client-domain.example
HANDSHAKE_TIMEOUT_S=20
TERMHOP_RELEASE=native
TRUSTED_PROXY_IPS=
MAX_CONNECTIONS_PER_IP=40
```

Then enable the service and configure the same TLS proxy shown above:

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now redis-server termhop-relay
sudo systemctl status termhop-relay
sudo journalctl -u termhop-relay -f
```

For upgrades, stop the relay, perform a fast-forward Git update, refresh the
venv with `python -m pip`, run tests, and restart. Avoid unattended updates of
a live terminal service.

## VPS starting profiles

These are conservative starting points, not benchmark guarantees. Terminal
output can be arbitrarily bursty; measure WebSocket bytes, event-loop latency,
Redis latency, memory, and reconnect rates on the real workload.

| Workload | vCPU | RAM | Disk | Network/transfer |
|---|---:|---:|---:|---|
| Development or one personal user | 1 | 1 GB | 10 GB SSD | 100 Mbps; 250 GB/month is usually ample |
| Small production, roughly 1–25 concurrent terminals | 2 | 2 GB | 20 GB SSD | 1 Gbps port or at least 1 TB/month |
| Growing deployment, roughly 25–100 concurrent terminals | 2–4 | 4 GB | 30 GB SSD | 1 Gbps and 2+ TB/month; load-test first |

Docker itself, Redis, the relay, the TLS proxy, logging, and OS page cache all
need headroom. A native personal relay may run below 1 GB, but 1 GB is the
recommended minimum. Add capacity for monitoring and backups. File transfer
or port-forward traffic, when enabled, changes bandwidth needs completely and
must be sized from measured peak throughput rather than terminal counts.

The Compose limits are deliberate: Docker containers otherwise have no CPU
or memory constraints by default. Redis should also have a configured ceiling
and be sized for peak, not average, resident memory. See Docker's
[resource-constraint guide](https://docs.docker.com/engine/containers/resource_constraints/)
and Redis's [memory guidance](https://redis.io/docs/latest/operate/oss_and_stack/management/optimization/memory-optimization/).

## Operational checklist

- Allow inbound 22 only from management addresses and inbound 443 publicly.
- Keep relay port 8080 and Redis 6379 bound to loopback/private networks.
- Configure TLS renewal and alert before certificate expiry.
- Set `TRUSTED_PROXY_IPS` to the exact address(es) your TLS proxy connects
  from, as seen by the relay process — never leave it unset while running
  behind a proxy. Left empty (the default), the relay ignores
  `X-Forwarded-For` entirely and rate-limits on the raw peer address, which
  in the Docker Compose topology is the container network's bridge gateway
  for every proxied connection, not the real client — this collapses per-IP
  pairing rate limits down to one shared bucket for all users. Find the
  correct value with `docker network inspect <project>_default` (look for
  the bridge `Gateway`), or run the proxy in the same custom Docker network
  as the relay and pin its container IP instead of relying on the gateway.
  Verify it by comparing `peer_ip` in relay logs against real distinct
  client addresses before relying on rate limiting in production.
- Leave `MAX_CONNECTIONS_PER_IP` (default 40) in place; it bounds concurrent
  sockets from one address regardless of whether they ever send a message.
- Monitor `/healthz`, container/service restarts, Redis errors, rate limits,
  open WebSockets, memory, CPU, disk, and network transfer.
- Rebuild images and rerun `pip-audit` after dependency changes — CI also
  runs `pip-audit` against every requirements file on a weekly schedule.
- Back up configuration, not transient Redis pairing/session data.
