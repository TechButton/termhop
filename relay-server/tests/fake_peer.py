# termhop relay tests — thin websocket-client wrapper standing in for a real
# agent or client (the relay never inspects payload contents, so tests can
# send arbitrary opaque strings as ciphertext/pubkey stand-ins).
import asyncio
import json
import time

import websockets


class FakePeer:
    def __init__(self, ws) -> None:
        self._ws = ws
        self._seq = 0

    @classmethod
    async def connect(cls, base_url: str, role: str) -> "FakePeer":
        ws = await websockets.connect(f"{base_url}/ws/{role}")
        return cls(ws)

    async def send(self, type_: str, *, session_id: str | None = None, payload: dict | None = None) -> None:
        self._seq += 1
        envelope = {
            "v": 2,
            "type": type_,
            "session_id": session_id,
            "seq": self._seq,
            "ts": int(time.time() * 1000),
            "payload": payload or {},
        }
        await self._ws.send(json.dumps(envelope))

    async def send_raw(self, raw: str) -> None:
        await self._ws.send(raw)

    async def recv(self, timeout: float = 5.0) -> dict:
        raw = await asyncio.wait_for(self._ws.recv(), timeout=timeout)
        return json.loads(raw) if isinstance(raw, str) else json.loads(raw.decode())

    async def close(self) -> None:
        await self._ws.close()

    @property
    def closed(self) -> bool:
        return self._ws.close_code is not None
