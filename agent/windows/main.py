"""Windows termhop-agent entry point."""

import sys

from common.cli import run_cli
from windows.pty_backend import PtyWindowsBackend


def main() -> int:
    return run_cli(
        backend_factory=PtyWindowsBackend,
        shell_env_var="COMSPEC",
        default_shell="cmd.exe",
    )


if __name__ == "__main__":
    sys.exit(main())
