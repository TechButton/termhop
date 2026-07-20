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
$AgentPython = "$InstallDir\agent\.venv\Scripts\python.exe"
$WrapperPath = "$BinDir\termhop-agent.bat"
$WatchPath = "$BinDir\termhop-agent-watch.bat"
$StartupLauncher = "$StartupDir\TermhopAgent.vbs"

function Assert-NativeSuccess {
    param([string]$Action)
    if ($LASTEXITCODE -ne 0) {
        throw "$Action failed with exit code $LASTEXITCODE."
    }
}

if (Test-Path "$InstallDir\.git") {
    Write-Host "Updating existing checkout at $InstallDir..."
    git -C $InstallDir pull --ff-only
    Assert-NativeSuccess "Git update"
} else {
    Write-Host "Cloning termhop into $InstallDir..."
    git clone --depth 1 $RepoUrl $InstallDir
    Assert-NativeSuccess "Git clone"
}

# Stop only processes whose command/executable resolves to this TermHop
# installation. The watcher must stop first or it will immediately respawn the
# agent while its virtual environment is being updated.
$TermhopProcesses = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)
$WatcherProcesses = @($TermhopProcesses | Where-Object {
    $_.CommandLine -and
    $_.CommandLine.IndexOf($WatchPath, [StringComparison]::OrdinalIgnoreCase) -ge 0
})
$AgentProcesses = @($TermhopProcesses | Where-Object {
    $_.CommandLine -and
    $_.CommandLine.IndexOf("-m windows.main", [StringComparison]::OrdinalIgnoreCase) -ge 0 -and
    (
        $_.CommandLine.IndexOf($AgentPython, [StringComparison]::OrdinalIgnoreCase) -ge 0 -or
        $_.CommandLine.IndexOf("$InstallDir\agent", [StringComparison]::OrdinalIgnoreCase) -ge 0
    )
})
$RestartBackgroundAfterUpdate = $WatcherProcesses.Count -gt 0
if ($WatcherProcesses.Count -gt 0 -or $AgentProcesses.Count -gt 0) {
    Write-Host "Stopping the existing TermHop background agent for update..."
    $WatcherProcesses | ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
    $AgentProcesses | ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
    # A venv executable cannot be replaced while any matching Windows process
    # still has it mapped. Wait for termination instead of relying on a fixed
    # delay, which was racy on slower machines and caused Errno 13 from pip.
    $StoppedIds = @($WatcherProcesses.ProcessId) + @($AgentProcesses.ProcessId)
    foreach ($ProcessId in $StoppedIds) {
        $Deadline = [DateTime]::UtcNow.AddSeconds(10)
        while (
            (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue) -and
            [DateTime]::UtcNow -lt $Deadline
        ) {
            Start-Sleep -Milliseconds 100
        }
    }
}

Push-Location "$InstallDir\agent"
try {
    if (-not (Test-Path $AgentPython)) {
        python -m venv .venv
        Assert-NativeSuccess "Virtual environment creation"
    }
    & $AgentPython -m pip install --quiet --upgrade pip
    Assert-NativeSuccess "pip upgrade"
    & $AgentPython -m pip install --quiet -r requirements-windows.txt
    Assert-NativeSuccess "TermHop dependency installation"
} finally {
    Pop-Location
}

New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
@"
@echo off
cd /d "$InstallDir\agent"
"$InstallDir\agent\.venv\Scripts\python.exe" -m windows.main %*
"@ | Set-Content -Path $WrapperPath -Encoding ASCII

New-Item -ItemType Directory -Force -Path $StartupDir | Out-Null
@"
@echo off
:reconnect
call "$WrapperPath" pair
timeout /t 5 /nobreak >nul
goto reconnect
"@ | Set-Content -Path $WatchPath -Encoding ASCII

# WScript starts the reconnect loop without leaving a console window open.
@"
Set Shell = CreateObject("WScript.Shell")
Shell.Run Chr(34) & "$WatchPath" & Chr(34), 0, False
"@ | Set-Content -Path $StartupLauncher -Encoding ASCII

$ConfigPath = "$env:APPDATA\termhop\config.toml"
$HasSavedPairing = (
    (Test-Path $ConfigPath) -and
    [bool](Select-String -Path $ConfigPath -Pattern '^\s*\[device\]\s*$' -Quiet)
)

Write-Host ""
Write-Host "Installed successfully."
if ($RestartBackgroundAfterUpdate -and $HasSavedPairing) {
    & "$env:SystemRoot\System32\wscript.exe" "$StartupLauncher"
    Write-Host "The previously running TermHop background agent was restarted."
} elseif ($HasSavedPairing) {
    Write-Host "A saved pairing was found; you do not need to pair again."
} else {
    Write-Host "Pair once from this PowerShell window:"
    Write-Host "  & `"$WrapperPath`" pair --relay wss://relay.yourdomain.com"
}
Write-Host ""
Write-Host "A no-admin per-user Startup launcher is installed at:"
Write-Host "       $StartupLauncher"
Write-Host "It reconnects automatically at your next login. To start the"
Write-Host "background reconnect loop now, after pairing, run:"
Write-Host "  & `"$env:SystemRoot\System32\wscript.exe`" `"$StartupLauncher`""
