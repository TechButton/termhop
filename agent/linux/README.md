# agent/linux

Linux PTY backend — `ptyprocess` / `os.forkpty`. Status: built (PROJECT_PLAN.md
step 2) — spawns one PTY, streams it encrypted to the relay, confirmed with a
real round-trip test (`agent/tests/test_end_to_end_linux.py`) and manually
against a live relay-server instance.

## Running

```bash
cd agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
termhop-agent pair --relay ws://localhost:8080   # via: python -m linux.main pair --relay ...
```

## Install as a systemd user service

`install.sh` clones the repo, sets up a venv, and installs
`termhop-agent.service`. After first pairing (so a relay URL is persisted):

```bash
systemctl --user enable --now termhop-agent
loginctl enable-linger $USER   # required for a *user* unit to run without
                                # an active login session — see DEPLOYMENT.md
```

## Known gaps (by design, this build step)

- **Every restart re-pairs from scratch.** No persisted long-term device
  key yet (see PROTOCOL.md's Encryption section) — a systemd restart
  generates a fresh pairing token/session, it does not resume the previous
  pairing. Fine for now, worth fixing before this is genuinely
  daily-usable.
- One PTY only — no `session_open`/`session_list`/multi-session support
  (PROJECT_PLAN.md step 3+).
- No idle-detection (`idle_alert`) or port forwarding — later steps.
- `session_resize` is accepted but only a real no-op stub is wired
  (`PTYBackend.resize()` calls `ptyprocess.setwinsize()` for real, but
  nothing sends `session_resize` yet since no client exists).
