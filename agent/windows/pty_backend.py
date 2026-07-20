# termhop agent (Windows) — pywinpty-based PTYBackend, wrapping ConPTY.
#
# Unlike POSIX ptyprocess, pywinpty's PtyProcess.read() is blocking
# synchronous I/O with no add_reader-equivalent hook into asyncio on
# Windows (there's no arbitrary-fd readiness notification the way POSIX
# select/epoll gives Linux/macOS). A small daemon-thread bridge is used instead
# of asyncio's default executor: a cancelled ConPTY read can remain blocked
# inside pywinpty, and asyncio.run() waits for default-executor workers during
# shutdown. That made session close and Ctrl+C appear to hang on Windows.
#
# Two things NOT verifiable in this Linux build environment — confirm on
# real Windows hardware before relying on them:
#   1. Whether pywinpty's read() raises EOFError on child exit, or returns
#      empty bytes/str instead. This code defensively raises EOFError
#      itself if read() returns falsy, so it's correct either way — but if
#      pywinpty raises its own EOFError first, that propagates through
#      run_in_executor's awaited future unchanged, also correct.
#   2. Whether write()/read() want `str` or `bytes` — ConPTY is UTF-16
#      under the hood, unlike POSIX byte-oriented ptys, and pywinpty's own
#      write(self, s) parameter name ("s") hints str may be expected on
#      some versions. If so, add a decode/encode shim at THIS boundary
#      (not in common/session_pump.py, which is platform-agnostic and
#      contracted to bytes per PTYBackend).
import asyncio
import threading

from winpty import PtyProcess

from common.ptybackend import PTYBackend


class PtyWindowsBackend(PTYBackend):
    def __init__(self) -> None:
        self._proc: PtyProcess | None = None

    def spawn(self, command: list[str], cwd: str | None = None) -> None:
        self._proc = PtyProcess.spawn(command, cwd=cwd)

    async def read(self, max_bytes: int = 65536) -> bytes:
        proc = self._proc
        assert proc is not None
        loop = asyncio.get_running_loop()

        # There is only one read coroutine in the session pump, so at most one
        # bridge thread exists for a backend at a time. If the coroutine is
        # cancelled, the daemon may remain in pywinpty briefly, but it cannot
        # hold up event-loop or interpreter shutdown. close() terminates the
        # ConPTY process to release it.
        completed: asyncio.Future[bytes | str] = loop.create_future()

        def finish_read(outcome: tuple[bool, bytes | str | BaseException]) -> None:
            if completed.done():
                return
            succeeded, value = outcome
            if succeeded:
                assert isinstance(value, (bytes, str))
                completed.set_result(value)
            else:
                assert isinstance(value, BaseException)
                completed.set_exception(value)

        def blocking_read() -> None:
            try:
                outcome: tuple[bool, bytes | str | BaseException] = (
                    True,
                    proc.read(max_bytes),
                )
            except BaseException as exc:
                outcome = (False, exc)
            try:
                loop.call_soon_threadsafe(finish_read, outcome)
            except RuntimeError:
                # The event loop can already be closed after cancellation.
                pass

        threading.Thread(
            target=blocking_read,
            name="termhop-conpty-read",
            daemon=True,
        ).start()
        data = await completed
        if not data:
            raise EOFError
        return data if isinstance(data, bytes) else data.encode("utf-8", errors="replace")

    def write(self, data: bytes) -> None:
        assert self._proc is not None
        # Same str-vs-bytes uncertainty as read() (see module docstring) —
        # try bytes first (matches the PTYBackend contract every other
        # backend uses), fall back to str if pywinpty's write() rejects it.
        # This is defensive because it can't be verified without real
        # Windows hardware; if this fallback ever actually triggers, prefer
        # simplifying to whichever branch pywinpty really wants once
        # confirmed, rather than keeping both paths indefinitely.
        try:
            self._proc.write(data)
        except TypeError:
            self._proc.write(data.decode("utf-8", errors="replace"))

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
