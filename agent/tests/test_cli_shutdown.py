"""Regression tests for clean foreground-agent shutdown."""

import sys
import unittest
from io import StringIO
from unittest.mock import patch

from common.cli import run_cli


class CliShutdownTests(unittest.TestCase):
    def test_ctrl_c_exits_without_traceback_and_keeps_pairing(self) -> None:
        def interrupt(coro):
            coro.close()
            raise KeyboardInterrupt

        with (
            patch.object(sys, "argv", ["termhop-agent", "pair"]),
            patch("common.cli.load_config") as load_config,
            patch("common.cli.asyncio.run", side_effect=interrupt),
            patch("sys.stdout", new_callable=StringIO) as stdout,
        ):
            load_config.return_value.relay_url = "wss://relay.example.com"
            result = run_cli(
                backend_factory=unittest.mock.Mock,
                shell_env_var="SHELL",
                default_shell="/bin/sh",
            )

        self.assertEqual(result, 130)
        self.assertIn("TermHop agent stopped", stdout.getvalue())
        self.assertIn("saved pairing was kept", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
