# termhop relay — async Redis connection pool wrapper.
from redis.asyncio import Redis


def make_redis(redis_url: str) -> Redis:
    return Redis.from_url(redis_url, decode_responses=True)
