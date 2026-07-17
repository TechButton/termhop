# termhop agent tests — real PTY spawn/attach/resize/exit-detection for
# the macOS backend. Runs directly in THIS Linux dev environment too,
# since PtyMacosBackend is pure POSIX ptyprocess/forkpty — identical code
# path to the Linux backend. This tests the shared POSIX pty logic for
# real; it does NOT test macOS-specific integration (Terminal.app,
# launchd, notarization) — those need real macOS hardware.
import asyncio

import pytest

from macos.pty_backend import PtyMacosBackend

pytestmark = pytest.mark.asyncio


async def test_spawn_echo_reads_output():
    backend = PtyMacosBackend()
    backend.spawn(["echo", "hello"])
    data = await backend.read()
    assert b"hello" in data
    backend.wait()


async def test_write_and_echo_round_trip():
    backend = PtyMacosBackend()
    backend.spawn(["cat"])
    backend.write(b"ping\n")
    data = await backend.read()
    assert b"ping" in data
    backend.close()


async def test_exit_code_captured():
    backend = PtyMacosBackend()
    backend.spawn(["sh", "-c", "exit 7"])
    with pytest.raises(EOFError):
        while True:
            await backend.read()
    assert backend.wait() == 7
    assert not backend.is_alive()


async def test_resize_does_not_raise():
    backend = PtyMacosBackend()
    backend.spawn(["cat"])
    backend.resize(40, 120)  # real ptyprocess call, just nothing drives it yet
    backend.close()


async def test_close_terminates_long_running_process():
    backend = PtyMacosBackend()
    backend.spawn(["sleep", "30"])
    assert backend.is_alive()
    backend.close()
    await asyncio.sleep(0.3)
    assert not backend.is_alive()
