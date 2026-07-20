# termhop relay — environment-driven configuration, single source of truth for tunables.
import os
from dataclasses import dataclass
from urllib.parse import urlsplit

PROTOCOL_VERSION = 2


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw else default


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    value = _env_int(name, default)
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


@dataclass(frozen=True)
class Config:
    domain: str
    redis_url: str
    pairing_token_ttl_s: int
    session_pending_ttl_s: int
    max_envelope_bytes: int
    protocol_version: int
    rate_limit_ip_max: int
    rate_limit_ip_window_s: int
    rate_limit_token_max: int
    token_min_len: int
    token_max_len: int
    handshake_timeout_s: int
    client_origins: tuple[str, ...]
    release: str

    @classmethod
    def from_env(cls) -> "Config":
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        if urlsplit(redis_url).scheme not in {"redis", "rediss", "unix"}:
            raise ValueError("REDIS_URL must use redis://, rediss://, or unix://")
        protocol_version = _env_int("PROTOCOL_VERSION", PROTOCOL_VERSION)
        if protocol_version != PROTOCOL_VERSION:
            raise ValueError(f"only protocol version {PROTOCOL_VERSION} is supported")
        origins = tuple(
            origin.strip().rstrip("/")
            for origin in os.environ.get(
                "CLIENT_ORIGINS",
                "https://client.42oclock.com,https://app.42oclock.com",
            ).split(",")
            if origin.strip()
        )
        if not origins or any(urlsplit(origin).scheme != "https" for origin in origins):
            raise ValueError("CLIENT_ORIGINS must contain one or more HTTPS origins")
        return cls(
            domain=os.environ.get("DOMAIN", "relay.example.com"),
            redis_url=redis_url,
            pairing_token_ttl_s=_bounded_int("PAIRING_TOKEN_TTL", 120, 30, 600),
            session_pending_ttl_s=_bounded_int("SESSION_PENDING_TTL", 60, 15, 600),
            max_envelope_bytes=_bounded_int(
                "MAX_ENVELOPE_BYTES", 262144, 4096, 1048576
            ),
            protocol_version=protocol_version,
            rate_limit_ip_max=_bounded_int("RATE_LIMIT_IP_MAX", 20, 1, 10000),
            rate_limit_ip_window_s=_bounded_int(
                "RATE_LIMIT_IP_WINDOW_S", 300, 1, 86400
            ),
            rate_limit_token_max=_bounded_int("RATE_LIMIT_TOKEN_MAX", 5, 1, 100),
            token_min_len=_bounded_int("TOKEN_MIN_LEN", 16, 16, 64),
            token_max_len=_bounded_int("TOKEN_MAX_LEN", 128, 32, 256),
            handshake_timeout_s=_bounded_int("HANDSHAKE_TIMEOUT_S", 20, 5, 120),
            client_origins=origins,
            release=os.environ.get("TERMHOP_RELEASE", "development"),
        )
