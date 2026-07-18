# termhop agent — agent-side pairing token + session_id generation. The relay
# never generates either value.
import secrets

_TOKEN_BYTES = 16  # secrets.token_urlsafe(16) -> ~22 url-safe chars, within
# relay's default 16-128 char bounds (relay-server/relay/config.py).
_PAIRING_SECRET_BYTES = 32


def generate_pairing_token() -> str:
    return secrets.token_urlsafe(_TOKEN_BYTES)


def generate_pairing_secret() -> str:
    """Return the out-of-band secret embedded in the pairing link.

    Unlike the routing token, this value is never sent to or stored by the
    relay. It authenticates the ECDH transcript and prevents a malicious relay
    from substituting either peer's public key.
    """
    return secrets.token_urlsafe(_PAIRING_SECRET_BYTES)


def generate_session_id() -> str:
    return f"sess-{secrets.token_hex(8)}"


def generate_device_id() -> str:
    """Return an unguessable routing identifier for one installed agent.

    The identifier is not an authentication secret. Reconnection is
    authenticated separately with the durable device secret and fresh ECDH.
    """
    return f"dev-{secrets.token_hex(16)}"
