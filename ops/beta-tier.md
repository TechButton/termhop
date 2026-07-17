# ops/beta-tier.md — termhop Beta Relay

Deployment notes for the **beta relay tier** — a small, permanent low-traffic
instance per the tiering plan in `PROJECT_PLAN.md` ("add a relay, don't
resize the one you have" — see decision log in `ops/DECISIONS.md`).

**Real host details (IP, hostname, SSH config) are intentionally not in
this file.** They live in `ops/beta-server.local.md`, which is gitignored.
Copy `ops/beta-server.local.md.example` to create it locally.

## Specs this tier is sized for

- 1 vCPU
- ~1.25 GB RAM
- 25 GB disk
- ~2.4 TB/month bandwidth
- Ubuntu 24.04

This is thin, not generous — see "Memory-constrained tuning" below. This
tier is meant for you plus a handful of early testers, not general
availability. See `PROJECT_PLAN.md` for the plan to add a second, larger
relay for broader use rather than growing this one.

## Prerequisites on the host

- [ ] Confirm no other service is still live on the box (see
      `ops/decommission-checklist.md` if repurposing a box that ran
      something before).
- [ ] Ubuntu 24.04, Docker + Docker Compose installed.
- [ ] A domain/subdomain pointed at the box — **do not configure agents
      or clients against a bare IP.** Use a low TTL (300s or less) on the
      DNS record from day one; this is what makes a future migration to a
      bigger box a DNS change instead of a reconfiguration of every
      paired device. See `PROJECT_PLAN.md`'s migration notes.
- [ ] Swap enabled. At 1.25 GB RAM, swap is not optional headroom — it's
      what turns a reconnect burst into graceful degradation instead of
      an OOM kill. See below.

## Add swap (if not already present)

```bash
# Check first — don't create a second swapfile if one exists
swapon --show
free -h

# If none, add 2GB:
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## Memory-constrained tuning

At ~1.25 GB total, both the relay process and Redis need explicit limits
so neither can starve the other or the host OS:

- **Redis**: cap `maxmemory` (see `docker-compose.yml` — the beta profile
  sets this explicitly rather than leaving it unbounded).
- **Container memory limits**: set `mem_limit` on both services in
  Compose so a leak or spike in one can't take down the whole box.
- **Connection ceiling**: until per-tenant rate limiting exists (tracked
  in `PROTOCOL.md`'s open questions), keep this tier invite-only and
  watch `free -m` during your first real test sessions rather than
  assuming headroom you haven't confirmed.

## Deploy

```bash
git clone <repo-url> termhop && cd termhop
cp ops/beta-server.local.md.example ops/beta-server.local.md   # fill in real host details, never committed
cp .env.example .env   # fill in DOMAIN, etc. — also gitignored
docker compose --profile beta up -d
```

(`docker-compose.yml`'s `beta` profile applies the memory limits above;
see the file for what changes between the default and beta profiles.)

## Monitoring, minimum viable

Nothing fancy needed yet — but at this RAM budget, check in on these
manually during early testing rather than finding out from a crash:

```bash
free -h                 # memory + swap headroom
docker stats --no-stream  # per-container memory/CPU
df -h                   # disk headroom (25GB fills faster than you'd think with logs)
```
