import unittest

from common.terminal_qr import render_pairing_qr


class TerminalQrTests(unittest.TestCase):
    def test_render_contains_quiet_zone_and_modules(self) -> None:
        value = "termhop://pair?relay=wss%3A%2F%2Frelay.example.com&token=token"
        rendered = render_pairing_qr(value)
        lines = rendered.splitlines()
        self.assertGreater(len(lines), 20)
        self.assertEqual(len({len(line) for line in lines}), 1)
        self.assertIn("██", rendered)
        self.assertIn("  ", rendered)


if __name__ == "__main__":
    unittest.main()
