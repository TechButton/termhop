# termhop agent tests — real PTY spawn/attach/resize/exit-detection for
# the Windows backend. Cannot run in this Linux build environment (needs
# real ConPTY) — skip-guarded so this file still collects cleanly
# everywhere; run for real on Windows to actually verify pywinpty's
# behavior, including the str-vs-bytes uncertainty flagged in
# windows/pty_backend.py's module docstring.
import asyncio
import sys

import pytest

pytestmark = [pytest.mark.asyncio, pytest.mark.skipif(sys.platform != "win32", reason="requires ConPTY")]

if sys.platform == "win32":
    from windows.pty_backend import PtyWindowsBackend


async def test_spawn_echo_reads_output():
    backend = PtyWindowsBackend()
    backend.spawn(["cmd.exe", "/c", "echo hello"])
    data = await backend.read()
    assert b"hello" in data
    backend.wait()


async def test_write_and_echo_round_trip():
    backend = PtyWindowsBackend()
    backend.spawn(["cmd.exe"])
    backend.write(b"echo ping\r\n")
    data = b""
    for _ in range(10):
        data += await backend.read()
        if b"ping" in data:
            break
    assert b"ping" in data
    backend.close()


async def test_exit_code_captured():
    backend = PtyWindowsBackend()
    backend.spawn(["cmd.exe", "/c", "exit 7"])
    with pytest.raises(EOFError):
        while True:
            await backend.read()
    assert backend.wait() == 7
    assert not backend.is_alive()


async def test_resize_does_not_raise():
    backend = PtyWindowsBackend()
    backend.spawn(["cmd.exe"])
    backend.resize(40, 120)
    backend.close()


async def test_close_terminates_long_running_process():
    backend = PtyWindowsBackend()
    backend.spawn(["cmd.exe", "/c", "timeout /t 30"])
    assert backend.is_alive()
    backend.close()
    await asyncio.sleep(0.3)
    assert not backend.is_alive()
