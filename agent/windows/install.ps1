# termhop Windows agent installer — matches DEPLOYMENT.md's documented flow:
#   irm https://raw.githubusercontent.com/.../agent/windows/install.ps1 | iex
#   termhop-agent pair --relay wss://relay.yourdomain.com
#
# No compiled .exe exists yet (that needs a PyInstaller-or-similar
# packaging step, out of scope here) — ships a .bat wrapper invoking the
# Python entry point directly, same "clone + venv" stopgap tier the
# Linux/macOS installers use, not a claim that DEPLOYMENT.md's .exe
# framing is already real.
#
# Scheduled-task-at-logon, not a real Windows Service: a true service
# needs pywin32's service framework (a new dependency not otherwise needed
# anywhere in this codebase) and typically runs as LocalSystem/a service
# account — a different privilege model than "runs under your own account"
# that Linux (systemd --user) and macOS (launchd per-user agent) already
# use. An AtLogon-triggered task with -RunLevel Limited (no elevation)
# matches that same per-user, no-admin-needed model.

$ErrorActionPreference = "Stop"

$RepoUrl = if ($env:TERMHOP_REPO_URL) { $env:TERMHOP_REPO_URL } else { "https://github.com/<you>/termhop.git" }
$InstallDir = if ($env:TERMHOP_INSTALL_DIR) { $env:TERMHOP_INSTALL_DIR } else { "$env:LOCALAPPDATA\termhop" }
$BinDir = "$env:LOCALAPPDATA\termhop\bin"
$TaskName = "TermhopAgent"

if (Test-Path "$InstallDir\.git") {
    Write-Host "Updating existing checkout at $InstallDir..."
    git -C $InstallDir pull --ff-only
} else {
    Write-Host "Cloning termhop into $InstallDir..."
    git clone --depth 1 $RepoUrl $InstallDir
}

Push-Location "$InstallDir\agent"
python -m venv .venv
& .venv\Scripts\pip.exe install --quiet --upgrade pip
& .venv\Scripts\pip.exe install --quiet -r requirements-windows.txt
Pop-Location

New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
$WrapperPath = "$BinDir\termhop-agent.bat"
@"
@echo off
cd /d "$InstallDir\agent"
"$InstallDir\agent\.venv\Scripts\python.exe" -m windows.main %*
"@ | Set-Content -Path $WrapperPath -Encoding ASCII

$Action = New-ScheduledTaskAction -Execute $WrapperPath -Argument "pair"
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

# Unregister first so re-running this installer is idempotent, matching
# the bootout-before-bootstrap pattern the macOS installer uses.
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -RunLevel Limited -Force | Out-Null

Write-Host ""
Write-Host "Installed. Next steps:"
Write-Host "  1. termhop-agent pair --relay wss://relay.yourdomain.com"
Write-Host "     (add $BinDir to your PATH, or call $WrapperPath directly)"
Write-Host "  2. The scheduled task '$TaskName' will run automatically at your"
Write-Host "     next logon, or start it now:"
Write-Host "       Start-ScheduledTask -TaskName $TaskName"
