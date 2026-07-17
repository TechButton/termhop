# termhop agent — persisted config, so systemd-unit restarts don't need
# --relay re-passed interactively. Only relay.url is persisted this build
# step (no keys — ephemeral-only per session, consistent with deferring the
# long-term device keypair). Reads via stdlib tomllib; writes are a
# hand-written TOML string since tomllib has no dump and this is one key.
import tomllib
from dataclasses import dataclass
from pathlib import Path

_CONFIG_DIR = Path.home() / ".config" / "termhop"
_CONFIG_PATH = _CONFIG_DIR / "config.toml"


@dataclass
class AgentConfig:
    relay_url: str | None = None


def load_config(path: Path = _CONFIG_PATH) -> AgentConfig:
    if not path.exists():
        return AgentConfig()
    with path.open("rb") as f:
        data = tomllib.load(f)
    return AgentConfig(relay_url=data.get("relay", {}).get("url"))


def save_config(config: AgentConfig, path: Path = _CONFIG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["[relay]"]
    if config.relay_url:
        escaped = config.relay_url.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'url = "{escaped}"')
    path.write_text("\n".join(lines) + "\n")
