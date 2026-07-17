# termhop relay — typed exceptions for pairing/routing/rate-limit failure paths.


class RelayError(Exception):
    """Base class for all relay-specific errors."""


class TokenExpired(RelayError):
    pass


class TokenAlreadyUsed(RelayError):
    pass


class TokenNotFound(RelayError):
    pass


class TokenInvalid(RelayError):
    """Malformed/too-short/too-long pairing token."""


class RateLimited(RelayError):
    def __init__(self, retry_after_s: float | None = None):
        super().__init__("rate limited")
        self.retry_after_s = retry_after_s


class SessionNotFound(RelayError):
    pass


class EnvelopeTooLarge(RelayError):
    pass


class EnvelopeInvalid(RelayError):
    """Malformed JSON or missing/mistyped required envelope fields."""


class ProtocolVersionMismatch(RelayError):
    def __init__(self, got: int, expected: int):
        super().__init__(f"protocol version {got} unsupported, expected {expected}")
        self.got = got
        self.expected = expected
