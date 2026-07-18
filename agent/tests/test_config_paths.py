# termhop agent tests — platform-specific config directory. Verifies the
# COMPUTED path per platform via monkeypatching sys.platform/env vars —
# doesn't need that OS actually present, since this is pure path-string
# logic, not filesystem access.
import os
from pathlib import Path

from common.config import AgentConfig, _config_dir, load_config, save_config


def test_linux_path(monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    assert _config_dir() == Path.home() / ".config" / "termhop"


def test_linux_honors_xdg_config_home(monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", "/tmp/custom-config")
    assert _config_dir() == Path("/tmp/custom-config/termhop")


def test_macos_path(monkeypatch):
    monkeypatch.setattr("sys.platform", "darwin")
    assert _config_dir() == Path.home() / "Library" / "Application Support" / "termhop"


def test_windows_path_with_appdata(monkeypatch):
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setenv("APPDATA", r"C:\Users\kyle\AppData\Roaming")
    assert _config_dir() == Path(r"C:\Users\kyle\AppData\Roaming") / "termhop"


def test_windows_path_without_appdata_falls_back(monkeypatch):
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.delenv("APPDATA", raising=False)
    assert _config_dir() == Path.home() / "AppData" / "Roaming" / "termhop"


def test_durable_device_config_round_trips_and_is_private(tmp_path):
    path = tmp_path / "config.toml"
    expected = AgentConfig(
        relay_url="wss://relay.example.com",
        device_id="dev-0123456789abcdef0123456789abcdef",
        device_secret="secret-value",
    )
    save_config(expected, path)
    assert load_config(path) == expected
    if os.name != "nt":
        assert path.stat().st_mode & 0o777 == 0o600
