# termhop relay — pairing-attempt rate limiting. Two independent limiters:
# per-IP (sliding window, resets naturally) and per-token (total-attempt cap,
# then permanent block for that token's remaining lifetime) — a brute-force
# burst against one leaked/guessed token gets stopped immediately rather than
# waiting out the token's TTL.
import time
import uuid

from redis.asyncio import Redis

from relay.config import Config
from relay.errors import RateLimited
from relay.pairing import token_digest

_IP_WINDOW_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local max = tonumber(ARGV[3])
local member = ARGV[4]
redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window_ms)
redis.call('ZADD', key, now, member)
redis.call('EXPIRE', key, math.ceil(window_ms / 1000) + 1)
local count = redis.call('ZCARD', key)
if count > max then
  return {'blocked', tostring(count)}
end
return {'ok', tostring(count)}
"""

_TOKEN_ATTEMPT_SCRIPT = """
local count_key = KEYS[1]
local block_key = KEYS[2]
local max = tonumber(ARGV[1])
local ttl = tonumber(ARGV[2])
if redis.call('EXISTS', block_key) == 1 then
  return {'blocked'}
end
local count = redis.call('INCR', count_key)
if count == 1 then
  redis.call('EXPIRE', count_key, ttl)
end
if count > max then
  redis.call('SET', block_key, '1', 'EX', ttl)
  return {'blocked'}
end
return {'ok', tostring(count)}
"""


async def check_ip_rate_limit(redis: Redis, cfg: Config, ip: str) -> None:
    now_ms = int(time.time() * 1000)
    member = f"{now_ms}:{uuid.uuid4().hex}"
    result = await redis.eval(  # type: ignore[misc]
        _IP_WINDOW_SCRIPT,
        1,
        f"relay:rl:ip:{ip}",
        str(now_ms),
        str(cfg.rate_limit_ip_window_s * 1000),
        str(cfg.rate_limit_ip_max),
        member,
    )
    if result[0] == "blocked":
        raise RateLimited(retry_after_s=cfg.rate_limit_ip_window_s)


async def check_token_rate_limit(redis: Redis, cfg: Config, token: str) -> None:
    digest = token_digest(token)
    result = await redis.eval(  # type: ignore[misc]
        _TOKEN_ATTEMPT_SCRIPT,
        2,
        f"relay:rl:token:{digest}",
        f"relay:rl:token_blocked:{digest}",
        str(cfg.rate_limit_token_max),
        str(cfg.pairing_token_ttl_s),
    )
    if result[0] == "blocked":
        raise RateLimited(retry_after_s=None)


class ConnectionLimiter:
    """In-process cap on concurrent WebSocket connections per (post-proxy) IP.

    Independent of the Redis-backed limiters above, which only guard pairing
    protocol messages: this bounds how many sockets one address can hold
    open before ever sending a message, so a connect-and-go-silent flood
    can't exhaust file descriptors/memory on its own.
    """

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    def try_acquire(self, ip: str, max_per_ip: int) -> bool:
        count = self._counts.get(ip, 0)
        if count >= max_per_ip:
            return False
        self._counts[ip] = count + 1
        return True

    def release(self, ip: str) -> None:
        count = self._counts.get(ip, 0)
        if count <= 1:
            self._counts.pop(ip, None)
        else:
            self._counts[ip] = count - 1
