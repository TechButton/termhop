# termhop agent — abstract PTY backend interface. Platform-specific
# implementations (agent/linux, later agent/macos/agent/windows) implement
# this; agent/common code (relay_client's streaming pump) depends only on
# this interface, never on a concrete backend.
from abc import ABC, abstractmethod


class PTYBackend(ABC):
    @abstractmethod
    def spawn(self, command: list[str], cwd: str | None = None) -> None:
        """Start the child process attached to a new PTY."""

    @abstractmethod
    async def read(self, max_bytes: int = 65536) -> bytes:
        """Read available output bytes. Raises EOFError when the child has
        exited and no more output remains."""

    @abstractmethod
    def write(self, data: bytes) -> None:
        """Write input bytes to the PTY (as if typed)."""

    def resize(self, rows: int, cols: int) -> None:
        """Stub for this build step — no session_resize sender exists yet.
        Concrete backends may implement this for real; the default no-op
        must not raise so unimplemented backends stay safe to call."""

    @abstractmethod
    def is_alive(self) -> bool:
        ...

    @abstractmethod
    def wait(self) -> int:
        """Blocks until the child exits, returns its exit code."""

    @abstractmethod
    def close(self) -> None:
        """Force-terminate the child and release the PTY fd if still open."""
