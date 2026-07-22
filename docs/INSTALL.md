# Install the TermHop agent

The web client runs at [client.42oclock.com](https://client.42oclock.com) and
does not require installation. The agent belongs on the computer whose terminal
you want to use remotely.

You need:

- Python 3.11 or newer;
- Git;
- a `wss://` TermHop relay URL reachable from the agent and browser; and
- a current browser with JavaScript enabled.

The installer creates a per-user checkout and Python virtual environment. It
does not require root or Administrator access. The first pairing command prints
a short-lived `termhop://pair?...` URL; treat that URL as a temporary secret.
The Linux installer checks these prerequisites before cloning anything and
prints the distribution-specific package command when Python's
`venv`/`ensurepip` support is missing.

## Linux

### 1. Install prerequisites

Ubuntu or Debian:

```sh
sudo apt update
sudo apt install -y git python3 python3-venv
python3 --version
git --version
```

Fedora:

```sh
sudo dnf install -y git python3
python3 --version
git --version
```

### 2. Install and pair

```sh
curl -fsSL https://raw.githubusercontent.com/TechButton/termhop/main/agent/linux/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
termhop-agent pair --relay wss://relay.example.com
```

The agent prints both the pairing URL and a terminal QR code. Scan the QR code
with the browser client's **Scan QR** option, or use the URL as a fallback. The
initial command runs in the foreground. Once pairing succeeds, press `Ctrl+C`;
the agent exits cleanly and keeps the saved pairing. Then start the persistent
per-user agent:

```sh
systemctl --user enable --now termhop-agent
systemctl --user status termhop-agent
```

You do not need to run `termhop-agent pair` again. The background service uses
the saved relay and device credentials automatically.

To keep it running when your Linux login session is closed:

```sh
sudo loginctl enable-linger "$USER"
```

Add this line to `~/.profile` if `$HOME/.local/bin` is not already on `PATH`:

```sh
export PATH="$HOME/.local/bin:$PATH"
```

Logs and control:

```sh
journalctl --user -u termhop-agent -n 100 --no-pager
systemctl --user restart termhop-agent
systemctl --user stop termhop-agent
```

## macOS

### 1. Install prerequisites

With Homebrew:

```sh
brew install python git
python3 --version
git --version
```

Python must report 3.11 or newer. Git supplied by Xcode Command Line Tools also
works.

### 2. Install and pair

```sh
curl -fsSL https://raw.githubusercontent.com/TechButton/termhop/main/agent/macos/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
termhop-agent pair --relay wss://relay.example.com
```

After the first terminal session ends, load the persistent per-user LaunchAgent:

```sh
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/io.termhop.agent.plist"
launchctl print "gui/$(id -u)/io.termhop.agent"
```

It runs at login and reconnects after a session ends. Logs are written to
`~/Library/Logs/termhop/`. To reload or stop it:

```sh
launchctl kickstart -k "gui/$(id -u)/io.termhop.agent"
launchctl bootout "gui/$(id -u)" "$HOME/Library/LaunchAgents/io.termhop.agent.plist"
```

## Windows 10 or 11

### 1. Install prerequisites

Install current 64-bit Python from python.org and select **Add python.exe to
PATH** during setup. Install Git for Windows, then open a new, ordinary
PowerShell window—Administrator mode is not required—and verify:

```powershell
python --version
git --version
```

Python must report 3.11 or newer.

### 2. Install and pair

```powershell
irm https://raw.githubusercontent.com/TechButton/termhop/main/agent/windows/install.ps1 | iex
& "$env:LOCALAPPDATA\termhop\bin\termhop-agent.bat" pair --relay wss://relay.example.com
```

The installer uses the virtual environment's Python to upgrade pip and install
packages. It creates a no-admin per-user Startup launcher rather than a
scheduled task, because scheduled-task creation may be blocked for standard
accounts. On an update, it stops only processes belonging to that TermHop
installation, reuses the existing virtual environment, and restarts the
background agent if it was already running.

After the first terminal session ends, start the hidden reconnect loop now:

```powershell
& "$env:SystemRoot\System32\wscript.exe" "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\TermhopAgent.vbs"
```

Keep the double quotes around both paths. Do not use literal single quotes if
launching the command from Command Prompt rather than PowerShell.

It will also start automatically at future logins. To confirm it is running:

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -like '*termhop-agent-watch.bat*' } |
  Select-Object ProcessId, CommandLine
```

If an older installer reported either “To modify pip, run ... python.exe -m
pip” or `Register-ScheduledTask: Access is denied`, rerun the current installer.
It updates the checkout and replaces the scheduled-task approach with the
per-user Startup launcher.

If an update reports `[Errno 13] Permission denied` for the venv's
`python.exe`, the raw GitHub response may have been cached or an older agent
may still hold the executable open. Run the freshly updated local installer so
its process-safe shutdown logic is used:

```powershell
& "$env:LOCALAPPDATA\termhop\agent\windows\install.ps1"
```

If it still fails, stop only the TermHop watcher and agent, then rerun that
local command:

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -like '*termhop-agent-watch.bat*' -or $_.CommandLine -like '*-m windows.main*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
& "$env:LOCALAPPDATA\termhop\agent\windows\install.ps1"
```

## Pair in the browser

1. Run `termhop-agent pair --relay wss://relay.example.com` using the command
   appropriate for your OS.
2. Open [client.42oclock.com](https://client.42oclock.com).
3. Choose **Pair your relay**.
4. Scan the displayed QR code, upload a QR image, or select **Paste URL** and
   paste the complete `termhop://pair?...` value.
5. Confirm the hostname and key fingerprint for manual pairings.

The agent saves a device credential only after both endpoints authenticate the
first handshake. The one-time pairing URL expires and cannot be used as a
long-lived login credential.

## Update

Rerun the installer for your operating system. It performs a fast-forward Git
update, refreshes the virtual environment, and rewrites the per-user launcher.
Restart the systemd user service, LaunchAgent, or Windows reconnect loop after
updating.

## Troubleshooting

- **`termhop-agent: command not found` on Linux/macOS:** add
  `$HOME/.local/bin` to `PATH`, or run `$HOME/.local/bin/termhop-agent`.
- **`python` is not recognized on Windows:** install Python with its PATH option
  enabled, then open a new PowerShell window.
- **`venv` cannot be created on Ubuntu/Debian:** install `python3-venv` (or the
  versioned package reported by the installer), then rerun the installer. If a
  previous attempt created an incomplete `.venv`, the installer detects and
  recreates only that TermHop environment.
- **Linux still prints the old `No module named pip` error after updating:**
  bypass a stale raw-content cache once by running the checked-out installer:

  ```sh
  sh "$HOME/.local/share/termhop/agent/linux/install.sh"
  ```
- **The relay cannot connect:** confirm the URL begins with `wss://`, its TLS
  certificate is valid, and both the browser and agent can reach it.
- **A saved device stays offline:** restart the OS-specific background agent and
  inspect its logs/status using the commands above.
- **Pairing fails after reusing an old link:** run the pairing command again; the
  previous token may have expired or already been consumed.
- **`Pairing failed: expected resume_init_ack, got error`:** the relay only
  allows one live connection per device at a time. This means the background
  agent (systemd user service / LaunchAgent / Windows startup task) is
  already running and holding that connection — running `termhop-agent pair`
  again in a separate terminal collides with it. Check first:

  ```sh
  systemctl --user status termhop-agent   # Linux
  launchctl list io.termhop.agent         # macOS
  ```

  If it's active, don't run `pair` manually — it's already reconnecting on
  its own. If it looks stuck, restart the service instead of running a second
  copy: `systemctl --user restart termhop-agent` (Linux) or the equivalent
  `launchctl kickstart` on macOS.

## Reset a device or move it to a different account

Every paired device has one durable credential, generated at pairing time and
saved to `~/.config/termhop/config.toml` (Linux/macOS) or the Windows
equivalent under `%APPDATA%`. As long as that credential exists, the agent
will only ever try to *resume* the account it was originally paired to — it
never re-pairs on its own, even after a restart.

To retire that credential and pair fresh (to the same account or a different
one), stop the background service first so it isn't also holding the old
connection, then run the pairing command with `--new-pairing`:

```sh
systemctl --user stop termhop-agent   # Linux; use the macOS/Windows equivalent from "Remove" below
termhop-agent pair --relay wss://relay.example.com --new-pairing
```

`--new-pairing` discards the saved `device_id`/secret and generates a brand
new one — the old device_id is now permanently orphaned (it never routes to
any working client again, since nothing remembers its secret) and can be
removed from the dashboard's attached-computers list. Scan the fresh QR code
or paste the fresh link from **whichever account's browser** you want this
computer linked to. Once paired, restart the background service so it starts
using the new saved credential automatically on boot:

```sh
systemctl --user start termhop-agent
```

If you don't want the agent on this machine anymore at all, see **Remove**
below instead of just clearing the credential.

## Remove

Linux:

```sh
systemctl --user disable --now termhop-agent
rm -f "$HOME/.config/systemd/user/termhop-agent.service" "$HOME/.local/bin/termhop-agent"
rm -rf "$HOME/.local/share/termhop"
```

macOS:

```sh
launchctl bootout "gui/$(id -u)" "$HOME/Library/LaunchAgents/io.termhop.agent.plist" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/io.termhop.agent.plist" "$HOME/.local/bin/termhop-agent"
rm -rf "$HOME/.local/share/termhop" "$HOME/Library/Logs/termhop"
```

Windows PowerShell:

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -like '*termhop-agent-watch.bat*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Remove-Item "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\TermhopAgent.vbs" -Force -ErrorAction SilentlyContinue
Remove-Item "$env:LOCALAPPDATA\termhop" -Recurse -Force
```
