# termhop relay — pairing token lifecycle and the Redis-backed session record.
#
# The relay never generates pairing tokens. It only accepts, validates, and
# atomically consumes whatever token string the agent chose. Consumption happens once, at
# successful pair_request+challenge delivery (see router.py) — not on
# pair_complete, since waiting for pair_complete would let an attacker's
# pair_request linger "pending" indefinitely by withholding it, extending the
# brute-force window past the token's TTL.
import re
import time
import hashlib
from typing import Awaitable, cast

from redis.asyncio import Redis

from relay.config import Config
from relay.errors import TokenAlreadyUsed, TokenInvalid, TokenNotFound

_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]+$")

_ISSUE_SCRIPT = """
local key = KEYS[1]
if redis.call('EXISTS', key) == 1 then
  return {'duplicate'}
end
redis.call('HSET', key, 'agent_pubkey', ARGV[1], 'session_id', ARGV[2], 'agent_hostname', ARGV[3], 'state', 'pending', 'created_at', ARGV[4])
redis.call('EXPIRE', key, ARGV[5])
return {'ok'}
"""

_CONSUME_SCRIPT = """
local key = KEYS[1]
if redis.call('EXISTS', key) == 0 then
  return {'not_found'}
end
local state = redis.call('HGET', key, 'state')
if state == 'consumed' then
  return {'already_used'}
end
redis.call('HSET', key, 'state', 'consumed')
local vals = redis.call('HGETALL', key)
return {'ok', unpack(vals)}
"""


def validate_token_format(token: str, cfg: Config) -> None:
    if not (
        isinstance(token, str)
        and cfg.token_min_len <= len(token) <= cfg.token_max_len
    ) or not _TOKEN_RE.match(token):
        raise TokenInvalid(
            f"token must be {cfg.token_min_len}-{cfg.token_max_len} url-safe chars"
        )


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def _token_key(token: str) -> str:
    return f"relay:token:{token_digest(token)}"


def _session_key(session_id: str) -> str:
    return f"relay:session:{session_id}"


async def issue_token(
    redis: Redis,
    cfg: Config,
    *,
    token: str,
    agent_pubkey: str,
    session_id: str,
    agent_hostname: str = "",
) -> None:
    validate_token_format(token, cfg)
    result = await redis.eval(  # type: ignore[misc]
        _ISSUE_SCRIPT,
        1,
        _token_key(token),
        agent_pubkey,
        session_id,
        agent_hostname,
        str(int(time.time() * 1000)),
        str(cfg.pairing_token_ttl_s),
    )
    if result[0] == "duplicate":
        raise TokenInvalid("token already in use")


async def consume_token(redis: Redis, token: str) -> dict[str, str]:
    """Atomically transitions a pending token to consumed and returns its
    fields (agent_pubkey, session_id, ...). Raises TokenNotFound (missing/
    expired) or TokenAlreadyUsed."""
    result = await redis.eval(_CONSUME_SCRIPT, 1, _token_key(token))  # type: ignore[misc]
    status = result[0]
    if status == "not_found":
        raise TokenNotFound(token)
    if status == "already_used":
        raise TokenAlreadyUsed(token)
    fields = result[1:]
    return dict(zip(fields[0::2], fields[1::2]))


async def delete_token(redis: Redis, token: str) -> None:
    await redis.delete(_token_key(token))


async def create_session_record(redis: Redis, cfg: Config, session_id: str) -> None:
    key = _session_key(session_id)
    await redis.hset(
        key,
        mapping={
            "state": "awaiting_client",
            "created_at": str(int(time.time() * 1000)),
        },
    )  # type: ignore[misc]
    await redis.expire(key, cfg.session_pending_ttl_s)  # type: ignore[misc]


async def set_session_state(redis: Redis, session_id: str, state: str) -> None:
    await redis.hset(_session_key(session_id), "state", state)  # type: ignore[misc]


async def mark_session_established(redis: Redis, session_id: str) -> None:
    key = _session_key(session_id)
    await redis.hset(key, "state", "established")  # type: ignore[misc]
    await redis.persist(key)  # type: ignore[misc]


async def get_session_state(redis: Redis, session_id: str) -> str | None:
    pending = cast(
        Awaitable[str | None], redis.hget(_session_key(session_id), "state")
    )
    return await pending


async def delete_session_record(redis: Redis, session_id: str) -> None:
    await redis.delete(_session_key(session_id))
