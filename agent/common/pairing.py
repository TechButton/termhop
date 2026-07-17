# termhop agent — agent-side pairing token + session_id generation. The
# relay never generates either of these (see SECURITY.md: "PC agent
# generates a single-use pairing token"; PROTOCOL.md's "Token and
# session-id ownership").
import secrets

_TOKEN_BYTES = 16  # secrets.token_urlsafe(16) -> ~22 url-safe chars, within
# relay's default 16-128 char bounds (relay-server/relay/config.py).


def generate_pairing_token() -> str:
    return secrets.token_urlsafe(_TOKEN_BYTES)


def generate_session_id() -> str:
    return f"sess-{secrets.token_hex(8)}"
