"""macOS termhop-agent entry point."""

import sys

from common.cli import run_cli
from macos.pty_backend import PtyMacosBackend


def main() -> int:
    return run_cli(
        backend_factory=PtyMacosBackend,
        shell_env_var="SHELL",
        default_shell="/bin/zsh",
    )


if __name__ == "__main__":
    sys.exit(main())
