# termhop relay — structured logging that is structurally incapable of
# emitting payload/ciphertext content. There is no parameter on this
# function shaped to accept it, so call sites physically cannot pass it
# through — this is enforced by the signature, not by review discipline.
# Every log call in relay/ must go through this function; test_no_plaintext_leak.py
# verifies no payload content ever reaches a log line.
import logging

_logger = logging.getLogger("relay")


def log_event(
    event: str,
    *,
    session_id: str | None = None,
    msg_type: str | None = None,
    byte_count: int | None = None,
    peer_ip: str | None = None,
    error: str | None = None,
) -> None:
    _logger.info(
        "event=%s session_id=%s msg_type=%s byte_count=%s peer_ip=%s error=%s",
        event,
        session_id,
        msg_type,
        byte_count,
        peer_ip,
        error,
    )
