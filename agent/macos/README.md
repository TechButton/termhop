# agent/macos

macOS PTY backend — same POSIX approach as `../linux` (`ptyprocess`/
`forkpty`), so this really was mostly a packaging task, per PROJECT_PLAN.md.
Status: built — `pty_backend.py` is a near-verbatim copy of the Linux
backend (renamed class only), tested for real in this repo's own
Linux-based CI/dev environment since `ptyprocess` is genuinely POSIX-
identical on both platforms (`agent/tests/test_pty_backend_macos.py`).

**Not verified on real macOS hardware yet** — the PTY logic itself is
proven (same code path Linux already runs), but `launchd` lifecycle
(`install.sh`, `termhop-agent.plist`), Terminal.app integration, and
`$SHELL`/zsh defaults have only been reviewed, not executed on a real Mac.

## Running

```bash
cd agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-macos.txt -r requirements-dev.txt
pytest
termhop-agent pair --relay wss://...   # via: python -m macos.main pair --relay ...
```

## Install as a launchd agent

```bash
curl -fsSL https://raw.githubusercontent.com/<you>/termhop/main/agent/macos/install.sh | sh
termhop-agent pair --relay wss://relay.yourdomain.com
```

This is the same "clone + venv" stopgap tier the Linux installer ships —
**not** the notarized `.app` or Homebrew formula DEPLOYMENT.md also
documents as the eventual real packaging path. Those need an Apple
Developer ID, notarization, and a `brew tap`, none of which exist yet.

`install.sh` installs `~/Library/LaunchAgents/io.termhop.agent.plist` and
loads it immediately via `launchctl bootstrap` (the modern API — not the
deprecated `load`/`unload`). Logs go to `~/Library/Logs/termhop/` since
launchd agents have no journal equivalent (`journalctl` has no macOS
counterpart).

## Known gaps (same as agent/linux, plus macOS-specific ones)

- Every restart re-pairs from scratch (no persisted long-term device key).
- One PTY only, no multi-session/idle-detection/port-forwarding (later
  PROJECT_PLAN.md steps).
- **Needs real hardware verification**: `launchctl bootstrap` actually
  loading correctly, the agent surviving logout/reboot, `KeepAlive`
  restarting after a crash, and zsh (`$SHELL` fallback) behaving as
  expected in Terminal.app/iTerm2.
