# termhop relay — in-process routing table: session_id -> live WebSocket
# pair. This never touches Redis; the actual WebSocket objects can't be
# serialized, and there's nothing to resume across a relay restart in v1;
# both ends must re-pair.
#
# Mutations are synchronous plain-dict operations with no `await` inside them,
# so there's no interleaving risk despite running under asyncio — each handler
# coroutine only ever touches the registry between awaits, never during one.
from dataclasses import dataclass

from fastapi import WebSocket

Role = str  # "agent" | "client"


def other_role(role: Role) -> Role:
    return "client" if role == "agent" else "agent"


@dataclass
class SessionSlot:
    agent: WebSocket | None = None
    client: WebSocket | None = None

    def get(self, role: Role) -> WebSocket | None:
        return self.agent if role == "agent" else self.client

    def set(self, role: Role, ws: WebSocket | None) -> None:
        if role == "agent":
            self.agent = ws
        else:
            self.client = ws

    def is_empty(self) -> bool:
        return self.agent is None and self.client is None


class SessionRegistry:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionSlot] = {}
        self._devices: dict[str, str] = {}

    def create(self, session_id: str) -> SessionSlot:
        slot = self._sessions.setdefault(session_id, SessionSlot())
        return slot

    def attach(self, session_id: str, role: Role, ws: WebSocket) -> SessionSlot:
        slot = self._sessions.setdefault(session_id, SessionSlot())
        existing = slot.get(role)
        if existing is not None and existing is not ws:
            raise ValueError(f"{role} is already attached to session {session_id}")
        slot.set(role, ws)
        return slot

    def get(self, session_id: str) -> SessionSlot | None:
        return self._sessions.get(session_id)

    def get_peer(self, session_id: str, role: Role) -> WebSocket | None:
        slot = self._sessions.get(session_id)
        if slot is None:
            return None
        return slot.get(other_role(role))

    def detach(self, session_id: str, role: Role) -> None:
        slot = self._sessions.get(session_id)
        if slot is None:
            return
        slot.set(role, None)
        if slot.is_empty():
            del self._sessions[session_id]

    def remove(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        for device_id, routed_session in list(self._devices.items()):
            if routed_session == session_id:
                del self._devices[device_id]

    def register_device(self, device_id: str, session_id: str) -> None:
        existing = self._devices.get(device_id)
        if existing is not None and existing != session_id:
            raise ValueError(f"device {device_id} is already connected")
        self._devices[device_id] = session_id

    def session_for_device(self, device_id: str) -> str | None:
        return self._devices.get(device_id)

    def __len__(self) -> int:
        return len(self._sessions)
