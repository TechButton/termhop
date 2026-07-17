# ops/decommission-checklist.md

For repurposing a box that previously ran something else — written with
the beta relay box in mind (an early/alpha RallyText instance, predating
the current RackNerd/Telnyx production stack), but generic enough for any
future reuse.

**Do not skip the "confirm nothing live" steps just because you're
confident it's dead.** The cost of checking is minutes; the cost of being
wrong on anything touching Safe Sport messaging infrastructure is not.

## 1. Confirm nothing is actually live

- [ ] Check for any DNS records still pointing at this host for the old
      service (not just the obvious domain — check for old subdomains,
      CNAMEs, or team-specific links that might have been shared
      directly rather than discovered via DNS).
- [ ] Check running processes/containers for anything from the old stack:
      ```bash
      docker ps -a
      systemctl list-units --type=service --state=running
      ps aux | grep -E 'gunicorn|flask|postgres|redis'
      ```
- [ ] Check for any cron jobs or scheduled tasks tied to the old service
      (`crontab -l`, `/etc/cron.d/`).
- [ ] If there's any doubt at all about whether a team might still be
      using this instance, confirm with whoever has visibility into
      current MCIC team communications before proceeding — not a step to
      shortcut given what the old service handled.

## 2. Clean shutdown of the old stack

- [ ] Stop and remove old containers/services (don't just `docker stop` —
      `docker compose down` or equivalent so nothing restarts on reboot).
- [ ] Note what old data existed (databases, uploaded files) and decide
      explicitly: archive it somewhere safe first, or confirm it's
      already superseded/backed up elsewhere and safe to discard. Don't
      let "probably fine to delete" be the default for anything that
      touched user data, even old/inactive user data.
- [ ] Remove old systemd unit files, old nginx/reverse-proxy configs, old
      cron entries — leftover config referencing dead services is a
      common source of confusing bugs later.

## 3. Baseline the box before installing anything new

```bash
free -h            # confirm RAM is actually freed up post-shutdown
df -h               # confirm disk space reclaimed
docker ps -a        # confirm empty (or only what you intend to keep)
sudo ufw status      # or iptables — check what's currently open
```

## 4. Then, and only then

Proceed with `ops/beta-tier.md` for the termhop relay setup.
