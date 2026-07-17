# agent/windows

Windows PTY backend — `pywinpty` (wraps ConPTY), required for real
color/cursor support in cmd.exe/PowerShell/claude.exe. Status: built —
`pty_backend.py`, `main.py`, `install.ps1` all written and reviewed, but
**none of it has been executed on real Windows** (this build environment
is Linux-only). `ruff`/`mypy` are clean; the actual ConPTY behavior is
unverified.

## Not yet verified on real Windows hardware

- Whether `pywinpty`'s `read()` raises `EOFError` on child exit or returns
  empty bytes/str (code handles either — see `pty_backend.py`'s docstring).
- Whether `read()`/`write()` want `str` or `bytes` (ConPTY is UTF-16
  internally, unlike POSIX ptys) — `pty_backend.py` has a defensive
  fallback for both directions, but the real behavior needs confirming.
- `pywinpty==2.0.*` actually installing cleanly (`pip install -r
  requirements-windows.txt`) — it's a native-extension wheel, can't be
  installed or import-checked on Linux at all.
- `install.ps1`'s `Register-ScheduledTask` actually registering, the task
  firing at logon, running in the interactive user's context (not a
  service account), and restarting after a crash. No `pwsh`/`powershell`
  exists in this build environment to even syntax-check the script.

## No compiled `.exe` yet

DEPLOYMENT.md's `termhop-agent.exe pair --relay wss://...` framing is
aspirational — that needs a PyInstaller-or-similar packaging step that
doesn't exist yet. `install.ps1` installs a `.bat` wrapper
(`%LOCALAPPDATA%\termhop\bin\termhop-agent.bat`) invoking
`python -m windows.main` directly, the same "clone + venv" stopgap tier
the Linux/macOS installers use.

## Packaging choice: scheduled task, not a Windows Service

A real Windows Service needs `pywin32`'s service framework (a new
dependency not otherwise used anywhere in this codebase) and typically
runs as `LocalSystem`/a service account — a different privilege model than
"runs under your own account," which Linux (systemd `--user`) and macOS
(launchd per-user agent) both already use. `install.ps1` registers an
`AtLogOn`-triggered scheduled task with `-RunLevel Limited` (no elevation
required) instead, matching that same per-user model.

## Running (once verified on real hardware)

```powershell
cd agent
python -m venv .venv
.venv\Scripts\pip install -r requirements-windows.txt -r requirements-dev.txt
.venv\Scripts\pytest
python -m windows.main pair --relay wss://relay.yourdomain.com
```

`agent/tests/test_pty_backend_windows.py` is skip-guarded
(`sys.platform != "win32"`) so it collects cleanly here but only actually
runs on real Windows — that's the file to run first to confirm the two
str-vs-bytes/EOFError unknowns above.

## Known gaps (same as agent/linux/agent/macos)

- Every restart re-pairs from scratch (no persisted long-term device key).
- One PTY only, no multi-session/idle-detection/port-forwarding.
- Default shell is `%COMSPEC%` (cmd.exe) — PowerShell/`claude.exe` shell
  selection is a future per-session feature, not this agent's default.
