# termhop agent tests — real PTY spawn/attach/resize/exit-detection. Runs
# directly since this dev environment is Linux.
import asyncio

import pytest

from linux.pty_backend import PtyLinuxBackend

pytestmark = pytest.mark.asyncio


async def test_spawn_echo_reads_output():
    backend = PtyLinuxBackend()
    backend.spawn(["echo", "hello"])
    data = await backend.read()
    assert b"hello" in data
    backend.wait()


async def test_write_and_echo_round_trip():
    backend = PtyLinuxBackend()
    backend.spawn(["cat"])
    backend.write(b"ping\n")
    data = await backend.read()
    assert b"ping" in data
    backend.close()


async def test_exit_code_captured():
    backend = PtyLinuxBackend()
    backend.spawn(["sh", "-c", "exit 7"])
    with pytest.raises(EOFError):
        while True:
            await backend.read()
    assert backend.wait() == 7
    assert not backend.is_alive()


async def test_resize_does_not_raise():
    backend = PtyLinuxBackend()
    backend.spawn(["cat"])
    backend.resize(40, 120)  # real ptyprocess call, just nothing drives it yet
    backend.close()


async def test_close_terminates_long_running_process():
    backend = PtyLinuxBackend()
    backend.spawn(["sleep", "30"])
    assert backend.is_alive()
    backend.close()
    await asyncio.sleep(0.3)
    assert not backend.is_alive()
