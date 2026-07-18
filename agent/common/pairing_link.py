# termhop agent — builds the termhop://pair pairing link/QR payload.
# Shared across all three platform agents (extracted from what was
# originally agent/linux/main.py's private _build_pairing_uri, duplicated
# logic that belongs in common/ per CONTRIBUTING.md's isolation rule).
import urllib.parse


def build_pairing_uri(
    relay_url: str,
    token: str,
    hostname: str,
    pairing_secret: str,
    agent_pubkey: str,
    session_id: str,
) -> str:
    """Build the authenticated v2 out-of-band pairing payload.

    ``token`` is only a relay routing handle. ``pairing_secret`` never appears
    in a relay envelope and authenticates the pinned agent key and client key.
    """
    query = urllib.parse.urlencode(
        {
            "relay": relay_url,
            "token": token,
            "secret": pairing_secret,
            "agent_key": agent_pubkey,
            "session": session_id,
            "hostname": hostname,
        }
    )
    return f"termhop://pair?{query}"
