"""Windows PTY cancellation regression tests runnable on any platform."""

import asyncio
import importlib
import sys
import threading
import types
import unittest


fake_winpty = types.ModuleType("winpty")
fake_winpty.PtyProcess = object
sys.modules.setdefault("winpty", fake_winpty)
windows_backend = importlib.import_module("windows.pty_backend")


class FakeProcess:
    def __init__(self, data: str = "hello") -> None:
        self.data = data
        self.read_started = threading.Event()
        self.release_read = threading.Event()
        self.alive = True

    def read(self, _max_bytes: int) -> str:
        self.read_started.set()
        self.release_read.wait()
        return self.data

    def isalive(self) -> bool:
        return self.alive

    def terminate(self, *, force: bool) -> None:
        self.alive = False
        self.release_read.set()


class WindowsPtyBackendTests(unittest.IsolatedAsyncioTestCase):
    async def test_read_does_not_use_default_executor(self) -> None:
        backend = windows_backend.PtyWindowsBackend()
        process = FakeProcess()
        backend._proc = process
        loop = asyncio.get_running_loop()

        original = loop.run_in_executor

        def reject_executor(*_args, **_kwargs):
            raise AssertionError("default executor must not be used for ConPTY reads")

        loop.run_in_executor = reject_executor
        try:
            read_task = asyncio.create_task(backend.read())
            while not process.read_started.is_set():
                await asyncio.sleep(0)
            process.release_read.set()
            self.assertEqual(await asyncio.wait_for(read_task, 1), b"hello")
        finally:
            loop.run_in_executor = original

    async def test_cancelled_read_does_not_wait_for_blocking_thread(self) -> None:
        backend = windows_backend.PtyWindowsBackend()
        process = FakeProcess()
        backend._proc = process

        read_task = asyncio.create_task(backend.read())
        while not process.read_started.is_set():
            await asyncio.sleep(0)
        read_task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await read_task

        backend.close()
        self.assertFalse(process.alive)


if __name__ == "__main__":
    unittest.main()
