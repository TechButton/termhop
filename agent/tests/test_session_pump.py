import unittest
from unittest.mock import AsyncMock, Mock

from common.envelope import Envelope
from common.session_pump import _pump_relay_to_pty


def _resize_envelope(rows: object, cols: object) -> Envelope:
    return Envelope(
        v=2, type="session_resize", session_id="sess-test", seq=1, ts=1,
        payload={"rows": rows, "cols": cols},
    )


async def _drain_one(envelope: Envelope, backend: Mock) -> None:
    client = Mock()
    client.recv_decrypted = AsyncMock(
        side_effect=[envelope, Envelope(
            v=2, type="session_close", session_id="sess-test", seq=2, ts=2, payload={},
        )]
    )
    await _pump_relay_to_pty(client, backend)


class SessionResizeValidationTests(unittest.IsolatedAsyncioTestCase):
    async def test_valid_dimensions_are_forwarded(self) -> None:
        backend = Mock()
        await _drain_one(_resize_envelope(24, 80), backend)
        backend.resize.assert_called_once_with(24, 80)

    async def test_non_integer_dimensions_are_rejected(self) -> None:
        backend = Mock()
        await _drain_one(_resize_envelope("24", "80"), backend)
        backend.resize.assert_not_called()

    async def test_out_of_range_dimensions_are_rejected(self) -> None:
        backend = Mock()
        await _drain_one(_resize_envelope(-1, 80), backend)
        backend.resize.assert_not_called()

    async def test_oversized_dimensions_are_rejected(self) -> None:
        backend = Mock()
        await _drain_one(_resize_envelope(100000, 80), backend)
        backend.resize.assert_not_called()

    async def test_boolean_dimensions_are_rejected(self) -> None:
        backend = Mock()
        await _drain_one(_resize_envelope(True, True), backend)
        backend.resize.assert_not_called()


if __name__ == "__main__":
    unittest.main()
