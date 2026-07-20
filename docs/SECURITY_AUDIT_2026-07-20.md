# Security and code audit — 2026-07-20

Scope: public relay, cross-platform agent, installers, deployment manifests,
hosted account/control plane, browser client, tenant provisioning, and the
disposable demo controller/image/firewall. Review methods included manual data
flow and state-machine analysis, strict-parser/adversarial tests, Python and npm
dependency audits, lint/type checks, unit tests, production builds, and live
Docker tenant-isolation tests.

## Remediated findings

- Updated vulnerable PyNaCl, cryptography, FastAPI/Starlette, Pydantic, Redis,
  Uvicorn, and python-dotenv dependency paths to audited fixed releases.
- Added an explicit relay session phase; terminal/control traffic is rejected
  until pairing or resume proofs finish.
- Added handshake deadlines, resume attempt limits, strict token/hostname,
  envelope, base64, key, nonce, ciphertext, URL, and configuration validation.
- Restricted browser WebSocket origins and transport message sizes.
- Made agent credential writes atomic and mode 0600 before publication.
- Added connection/open/ping/close bounds and browser queue/handshake bounds to
  prevent silent memory or connection exhaustion.
- Hardened Docker runtime settings and added a hardened native systemd unit.
- Made all OS installer updates reuse venvs and stop/restart live agents safely.
- In the hosted tier, stopped trusting arbitrary `X-Forwarded-For`, added
  cross-site mutation rejection and security headers, hashed database session
  identifiers, bounded request/credential inputs, bound tenant relay ports to
  loopback, and made failed provisioning records retryable.

## Residual risks and limitations

- The browser client and hosted tier are maintained in a separate private
  repository; public users can audit the relay and agent but not hosted code.
- Browser-local durable credentials remain accessible to code executing in the
  trusted client origin. Strong static-host CSP and dependency hygiene are
  therefore mandatory; encryption cannot protect against same-origin XSS.
- The hosted provisioner currently requires root-equivalent Docker control.
  It must remain on a dedicated host. Separating it into a narrow internal
  provisioner service is recommended before broader production use.
- Per-tenant public TLS routing/provisioning is incomplete; never expose the
  generated plaintext relay port. Loopback binding is now enforced.
- A holder of a valid device identifier can trigger a resume handshake and
  cause bounded denial of service, but cannot authenticate or decrypt without
  the 256-bit device secret. Rate limits and handshake deadlines bound impact.
- Python/JavaScript cannot guarantee immediate zeroization of key material.
- This review reduces known risk; it is not a proof that no vulnerability
  exists. Repeat after protocol, dependency, infrastructure, or auth changes.

## Verification gates

- Python dependency audit: no known vulnerabilities after updated pins.
- npm audit: no known vulnerabilities.
- Agent security/unit tests, relay security tests, lint, and mypy: pass.
- Hosted backend tests (including real Redis and Docker tenant isolation): pass.
- Browser unit tests and production Vite build: pass.
