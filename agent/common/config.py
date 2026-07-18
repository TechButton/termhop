# termhop agent — persisted config, so a restart doesn't need --relay
# re-passed interactively. Only relay.url is persisted this build step (no
# keys — ephemeral-only per session, consistent with deferring the
# long-term device keypair). Reads via stdlib tomllib; writes are a
# hand-written TOML string since tomllib has no dump and this is one key.
#
# Config directory is platform-specific (Linux XDG, macOS Application
# Support, Windows %APPDATA%) despite this module living in common/ — it's
# genuinely shared *logic* (the load/save/TOML handling), just with a
# per-OS path. Computed at call time, not bound as a module-level default
# argument, so tests can monkeypatch sys.platform and see it take effect —
# a `path: Path = SOME_CONSTANT` default only evaluates once at import.
import os
import sys
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
    path.write_text("\n".join(lines) + "\n")
    # The durable device credential grants terminal access. Restrict it to
    # the installing OS user even if their default umask is permissive.
    if os.name != "nt":
        path.chmod(0o600)
