# termhop agent — builds the termhop://pair pairing link/QR payload.
# Shared across all three platform agents (extracted from what was
# originally agent/linux/main.py's private _build_pairing_uri, duplicated
# logic that belongs in common/ per CONTRIBUTING.md's isolation rule).
import urllib.parse


def build_pairing_uri(relay_url: str, token: str, hostname: str) -> str:
    """termhop://pair?relay=...&token=...&hostname=... — see
    client/src/lib/pairingLink.js for the decoder this must match exactly."""
    query = urllib.parse.urlencode({"relay": relay_url, "token": token, "hostname": hostname})
    return f"termhop://pair?{query}"
