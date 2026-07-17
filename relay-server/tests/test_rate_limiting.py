# termhop relay tests — per-IP sliding-window and per-token attempt-cap limiters.
import asyncio

import pytest

from relay.errors import RateLimited
from relay.ratelimit import check_ip_rate_limit, check_token_rate_limit

pytestmark = pytest.mark.asyncio


async def test_ip_limit_allows_up_to_max(redis_client, test_config):
    for _ in range(test_config.rate_limit_ip_max):
        await check_ip_rate_limit(redis_client, test_config, "1.2.3.4")


async def test_ip_limit_blocks_over_max(redis_client, test_config):
    for _ in range(test_config.rate_limit_ip_max):
        await check_ip_rate_limit(redis_client, test_config, "1.2.3.5")
    with pytest.raises(RateLimited):
        await check_ip_rate_limit(redis_client, test_config, "1.2.3.5")


async def test_ip_limit_resets_after_window(redis_client, test_config):
    for _ in range(test_config.rate_limit_ip_max):
        await check_ip_rate_limit(redis_client, test_config, "1.2.3.6")
    await asyncio.sleep(test_config.rate_limit_ip_window_s + 0.5)
    await check_ip_rate_limit(redis_client, test_config, "1.2.3.6")


async def test_ip_limits_dont_cross_contaminate(redis_client, test_config):
    for _ in range(test_config.rate_limit_ip_max):
        await check_ip_rate_limit(redis_client, test_config, "9.9.9.1")
    # a different IP is unaffected
    await check_ip_rate_limit(redis_client, test_config, "9.9.9.2")


async def test_token_limit_blocks_after_max_attempts(redis_client, test_config):
    token = "tok_ratelimit_a"
    for _ in range(test_config.rate_limit_token_max):
        await check_token_rate_limit(redis_client, test_config, token)
    with pytest.raises(RateLimited):
        await check_token_rate_limit(redis_client, test_config, token)


async def test_token_limit_stays_blocked_even_below_ttl(redis_client, test_config):
    token = "tok_ratelimit_b"
    for _ in range(test_config.rate_limit_token_max + 1):
        try:
            await check_token_rate_limit(redis_client, test_config, token)
        except RateLimited:
            pass
    with pytest.raises(RateLimited):
        await check_token_rate_limit(redis_client, test_config, token)


async def test_token_limits_dont_cross_contaminate(redis_client, test_config):
    for _ in range(test_config.rate_limit_token_max):
        await check_token_rate_limit(redis_client, test_config, "tok_ratelimit_c")
    await check_token_rate_limit(redis_client, test_config, "tok_ratelimit_d")
