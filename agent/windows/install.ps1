# termhop Windows agent installer:
#   irm https://raw.githubusercontent.com/.../agent/windows/install.ps1 | iex
#   termhop-agent pair --relay wss://relay.yourdomain.com
#
# This installer uses a venv-managed checkout and per-user Startup launcher.
# It deliberately requires no administrator rights. Scheduled-task creation is
# denied by policy on some otherwise-supported Windows accounts.

$ErrorActionPreference = "Stop"

$RepoUrl = if ($env:TERMHOP_REPO_URL) { $env:TERMHOP_REPO_URL } else { "https://github.com/TechButton/termhop.git" }
$InstallDir = if ($env:TERMHOP_INSTALL_DIR) { $env:TERMHOP_INSTALL_DIR } else { "$env:LOCALAPPDATA\termhop" }
$BinDir = "$env:LOCALAPPDATA\termhop\bin"
$StartupDir = [Environment]::GetFolderPath("Startup")

if (Test-Path "$InstallDir\.git") {
    Write-Host "Updating existing checkout at $InstallDir..."
    git -C $InstallDir pull --ff-only
} else {
    Write-Host "Cloning termhop into $InstallDir..."
    git clone --depth 1 $RepoUrl $InstallDir
}

Push-Location "$InstallDir\agent"
python -m venv .venv
& .venv\Scripts\python.exe -m pip install --quiet --upgrade pip
& .venv\Scripts\python.exe -m pip install --quiet -r requirements-windows.txt
Pop-Location

New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
$WrapperPath = "$BinDir\termhop-agent.bat"
@"
@echo off
cd /d "$InstallDir\agent"
"$InstallDir\agent\.venv\Scripts\python.exe" -m windows.main %*
"@ | Set-Content -Path $WrapperPath -Encoding ASCII

New-Item -ItemType Directory -Force -Path $StartupDir | Out-Null
$WatchPath = "$BinDir\termhop-agent-watch.bat"
@"
@echo off
:reconnect
call "$WrapperPath" pair
timeout /t 5 /nobreak >nul
goto reconnect
"@ | Set-Content -Path $WatchPath -Encoding ASCII

# WScript starts the reconnect loop without leaving a console window open.
$StartupLauncher = "$StartupDir\TermhopAgent.vbs"
@"
Set Shell = CreateObject("WScript.Shell")
Shell.Run Chr(34) & "$WatchPath" & Chr(34), 0, False
"@ | Set-Content -Path $StartupLauncher -Encoding ASCII

Write-Host ""
Write-Host "Installed. Next steps:"
Write-Host "  1. Pair once from this PowerShell window:"
Write-Host "       & `"$WrapperPath`" pair --relay wss://relay.yourdomain.com"
Write-Host "  2. A no-admin per-user Startup launcher is installed at:"
Write-Host "       $StartupLauncher"
Write-Host "     It reconnects automatically at your next login. To start the"
Write-Host "     background reconnect loop now, after pairing, run:"
Write-Host "       & `"$env:SystemRoot\System32\wscript.exe`" `"$StartupLauncher`""
