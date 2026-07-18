# termhop agent tests — pairing URI builder, shared across all platform
# agents. Cross-checked against client/src/lib/pairingLink.js's decoder in
# a previous build step (confirmed round-tripping there); this test covers
# the Python side in isolation.
import urllib.parse

from common.pairing_link import build_pairing_uri


def test_build_pairing_uri_round_trips():
    uri = build_pairing_uri(
        "wss://relay.example.com",
        "tok_abc123",
        "my-host",
        "pair-secret",
        "agent-pub",
        "sess-1",
    )
    assert uri.startswith("termhop://pair?")

    query = uri.split("?", 1)[1]
    params = urllib.parse.parse_qs(query)
    assert params["relay"] == ["wss://relay.example.com"]
    assert params["token"] == ["tok_abc123"]
    assert params["hostname"] == ["my-host"]
    assert params["secret"] == ["pair-secret"]
    assert params["agent_key"] == ["agent-pub"]
    assert params["session"] == ["sess-1"]


def test_build_pairing_uri_percent_encodes_relay_url():
    uri = build_pairing_uri(
        "wss://relay.example.com:8080/x?y=1",
        "t",
        "h",
        "secret",
        "pub",
        "sess",
    )
    assert "wss://relay.example.com:8080/x?y=1" not in uri
    params = urllib.parse.parse_qs(uri.split("?", 1)[1])
    assert params["relay"] == ["wss://relay.example.com:8080/x?y=1"]
