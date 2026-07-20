# Security policy and model

See [the code reference](docs/CODE_REFERENCE.md),
[relay deployment guide](docs/RELAY_DEPLOYMENT.md), and
[2026-07-20 audit](docs/SECURITY_AUDIT_2026-07-20.md).

Terminal plaintext and durable device credentials are end-to-end encrypted
between the browser and agent. The relay sees IP addresses, timing, hostname,
session/device identifiers, message types, sizes, and ciphertext. A malicious
relay can observe metadata, delay/drop traffic, and deny service, but endpoint
proofs prevent it from substituting keys without detection.

Treat a pairing URI as a short-lived secret and a saved device secret as a
long-lived terminal credential. Compromise of the OS user, browser origin,
browser storage, or installed agent files is outside the protection supplied
by transport encryption.

Report vulnerabilities privately to the maintainer before opening a public
issue. Include affected commit, reproduction, impact, and suggested mitigation.
