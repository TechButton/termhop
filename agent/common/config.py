# termhop agent — persisted config, so a restart doesn't need --relay
# re-passed interactively. The relay URL and durable device credential are
# stored after pairing. Reads use stdlib tomllib; writes are hand-written TOML
# because tomllib has no dump support and the schema is intentionally tiny.
#
# Config directory is platform-specific (Linux XDG, macOS Application
# Support, Windows %APPDATA%) despite this module living in common/ — it's
# genuinely shared *logic* (the load/save/TOML handling), just with a
# per-OS path. Computed at call time, not bound as a module-level default
# argument, so tests can monkeypatch sys.platform and see it take effect —
# a `path: Path = SOME_CONSTANT` default only evaluates once at import.
import os
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path


def _config_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "termhop"
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        return base / "termhop"
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg_config_home) if xdg_config_home else Path.home() / ".config"
    return base / "termhop"


def _config_path() -> Path:
    return _config_dir() / "config.toml"


@dataclass
class AgentConfig:
    relay_url: str | None = None
    device_id: str | None = None
    device_secret: str | None = None


def load_config(path: Path | None = None) -> AgentConfig:
    path = path or _config_path()
    if not path.exists():
        return AgentConfig()
    with path.open("rb") as f:
        data = tomllib.load(f)
    return AgentConfig(
        relay_url=data.get("relay", {}).get("url"),
        device_id=data.get("device", {}).get("id"),
        device_secret=data.get("device", {}).get("secret"),
    )


def save_config(config: AgentConfig, path: Path | None = None) -> None:
    path = path or _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["[relay]"]
    if config.relay_url:
        escaped = config.relay_url.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'url = "{escaped}"')
    if config.device_id and config.device_secret:
        lines.extend(
            [
                "",
                "[device]",
                f'id = "{config.device_id}"',
                f'secret = "{config.device_secret}"',
            ]
        )
    # Write to a mode-0600 temporary file and atomically replace the config.
    # This avoids a first-write window where a permissive umask could expose
    # the durable device credential before a later chmod call.
    fd, temporary_name = tempfile.mkstemp(prefix=".config-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        if os.name != "nt":
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            fd = -1  # fdopen owns and closes the descriptor from this point.
            handle.write("\n".join(lines) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        if fd >= 0:
            os.close(fd)
        temporary.unlink(missing_ok=True)
        raise
