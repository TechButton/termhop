# termhop relay — environment-driven configuration, single source of truth for tunables.
import os
from dataclasses import dataclass


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw else default


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

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            domain=os.environ.get("DOMAIN", "relay.example.com"),
            redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
            pairing_token_ttl_s=_env_int("PAIRING_TOKEN_TTL", 120),
            session_pending_ttl_s=_env_int("SESSION_PENDING_TTL", 60),
            max_envelope_bytes=_env_int("MAX_ENVELOPE_BYTES", 262144),
            protocol_version=_env_int("PROTOCOL_VERSION", 1),
            rate_limit_ip_max=_env_int("RATE_LIMIT_IP_MAX", 20),
            rate_limit_ip_window_s=_env_int("RATE_LIMIT_IP_WINDOW_S", 300),
            rate_limit_token_max=_env_int("RATE_LIMIT_TOKEN_MAX", 5),
            token_min_len=_env_int("TOKEN_MIN_LEN", 16),
            token_max_len=_env_int("TOKEN_MAX_LEN", 128),
        )
