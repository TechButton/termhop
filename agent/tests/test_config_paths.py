# termhop agent tests — platform-specific config directory. Verifies the
# COMPUTED path per platform via monkeypatching sys.platform/env vars —
# doesn't need that OS actually present, since this is pure path-string
# logic, not filesystem access.
from pathlib import Path

from common.config import _config_dir


def test_linux_path(monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")
    assert _config_dir() == Path.home() / ".config" / "termhop"


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
