# termhop relay tests — pairing token issue/consume/expiry/reuse-rejection.
import asyncio

import pytest

from relay.errors import TokenAlreadyUsed, TokenInvalid, TokenNotFound
from relay.pairing import consume_token, issue_token, validate_token_format

@pytest.mark.asyncio
async def test_issue_then_consume_succeeds(redis_client, test_config):
    await issue_token(
        redis_client, test_config, token="tok_" + "a" * 12, agent_pubkey="PUBKEY", session_id="sess1"
    )
    fields = await consume_token(redis_client, "tok_" + "a" * 12)
    assert fields["agent_pubkey"] == "PUBKEY"
    assert fields["session_id"] == "sess1"
    assert fields["state"] == "consumed"


@pytest.mark.asyncio
async def test_second_consume_rejected(redis_client, test_config):
    token = "tok_" + "b" * 12
    await issue_token(redis_client, test_config, token=token, agent_pubkey="PUB", session_id="s2")
    await consume_token(redis_client, token)
    with pytest.raises(TokenAlreadyUsed):
        await consume_token(redis_client, token)


@pytest.mark.asyncio
async def test_unknown_token_rejected(redis_client, test_config):
    with pytest.raises(TokenNotFound):
        await consume_token(redis_client, "tok_" + "z" * 12)


@pytest.mark.asyncio
async def test_expiry(redis_client, test_config):
    token = "tok_" + "c" * 12
    await issue_token(redis_client, test_config, token=token, agent_pubkey="PUB", session_id="s3")
    await asyncio.sleep(test_config.pairing_token_ttl_s + 0.5)
    with pytest.raises(TokenNotFound):
        await consume_token(redis_client, token)


@pytest.mark.asyncio
async def test_duplicate_pending_token_rejected(redis_client, test_config):
    token = "tok_" + "d" * 12
    await issue_token(redis_client, test_config, token=token, agent_pubkey="PUB", session_id="s4")
    with pytest.raises(TokenInvalid):
        await issue_token(redis_client, test_config, token=token, agent_pubkey="PUB2", session_id="s5")


@pytest.mark.parametrize("bad_token", ["short", "has spaces here", "x" * 200, "has/slash"])
def test_malformed_token_format_rejected(bad_token, test_config):
    with pytest.raises(TokenInvalid):
        validate_token_format(bad_token, test_config)
