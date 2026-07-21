# termhop agent (Linux) — ptyprocess-based PTYBackend, wrapping os.forkpty.
# session_resize is a real one-line ptyprocess call (setwinsize), but
# nothing drives it yet — no client sends session_resize in this build step.
import asyncio

import ptyprocess

from common.ptybackend import PTYBackend


class PtyLinuxBackend(PTYBackend):
    def __init__(self) -> None:
        self._proc: ptyprocess.PtyProcess | None = None

    def spawn(
        self,
        command: list[str],
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self._proc = ptyprocess.PtyProcess.spawn(command, cwd=cwd, env=env)

    async def read(self, max_bytes: int = 65536) -> bytes:
        proc = self._proc
        assert proc is not None
        loop = asyncio.get_running_loop()
        future: asyncio.Future[bytes] = loop.create_future()

        def _on_readable() -> None:
            loop.remove_reader(proc.fd)
            try:
                data = proc.read(max_bytes)
                if not future.done():
                    future.set_result(data)
            except EOFError as exc:
                if not future.done():
                    future.set_exception(exc)

        loop.add_reader(proc.fd, _on_readable)
        try:
            return await future
        finally:
            try:
                loop.remove_reader(proc.fd)
            except (ValueError, OSError):
                pass

    def write(self, data: bytes) -> None:
        assert self._proc is not None
        self._proc.write(data)

    def resize(self, rows: int, cols: int) -> None:
        assert self._proc is not None
        self._proc.setwinsize(rows, cols)

    def is_alive(self) -> bool:
        assert self._proc is not None
        return self._proc.isalive()

    def wait(self) -> int:
        assert self._proc is not None
        return self._proc.wait()

    def close(self) -> None:
        if self._proc is not None and self._proc.isalive():
            self._proc.terminate(force=True)
