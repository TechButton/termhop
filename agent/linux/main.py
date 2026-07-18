"""Linux termhop-agent entry point."""

import sys

from common.cli import run_cli
from linux.pty_backend import PtyLinuxBackend


def main() -> int:
    return run_cli(
        backend_factory=PtyLinuxBackend,
        shell_env_var="SHELL",
        default_shell="/bin/bash",
    )


if __name__ == "__main__":
    sys.exit(main())
