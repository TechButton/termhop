# termhop agent tests — envelope round-trip, matching relay's exact model.
import pytest

from common.envelope import EnvelopeError, dump_envelope, parse_envelope


def test_round_trip():
    raw = '{"v":1,"type":"pty_data","session_id":"s1","seq":1,"ts":123,"payload":{"nonce":"a","ciphertext":"b"}}'
    envelope = parse_envelope(raw)
    assert envelope.type == "pty_data"
    assert envelope.session_id == "s1"
    assert envelope.payload == {"nonce": "a", "ciphertext": "b"}
    assert dump_envelope(envelope) == raw.replace(" ", "")


def test_null_session_id_for_pre_pairing():
    envelope = parse_envelope('{"v":1,"type":"pair_init","session_id":null,"seq":1,"ts":1,"payload":{}}')
    assert envelope.session_id is None


def test_malformed_json_rejected():
    with pytest.raises(EnvelopeError):
        parse_envelope("not json")


def test_missing_required_field_rejected():
    with pytest.raises(EnvelopeError):
        parse_envelope('{"v":1,"type":"pair_init"}')


def test_default_empty_payload():
    envelope = parse_envelope('{"v":1,"type":"pair_complete","session_id":"s1","seq":1,"ts":1}')
    assert envelope.payload == {}
