# Contributing to termhop

Thanks for considering contributing. This project handles remote command
execution and terminal content, so a few things are stricter here than a
typical open-source project — please read before opening a PR.

## Ground Rules

1. **No plaintext-transport modes.** Any PR that adds a way to run agent↔relay↔client traffic without the ECDH-derived encryption will be closed. See `SECURITY.md` for why this is non-negotiable.
2. **No hand-rolled crypto.** Use vetted libraries (`pynacl`/`libsodium`, `cryptography`) for anything touching the handshake or session encryption. New crypto primitives or custom implementations need explicit maintainer sign-off and ideally external review before merge.
3. **No new default-on auto-accept / skip-permission behavior.** If a feature can cause the agent to execute commands without a human confirming, it must default off and be clearly labeled in the client UI when enabled.
4. **No inbound listeners added to the agent by default.** The agent's outbound-only connection model is a core security property, not an implementation detail — features that require an inbound port need a strong justification and explicit opt-in.

## Getting Started

```bash
git clone https://github.com/<you>/termhop
cd termhop
# relay-server: Python 3.11+, FastAPI
cd relay-server && pip install -r requirements-dev.txt
# agent: Python 3.11+, platform-specific PTY deps
cd ../agent && pip install -r requirements-dev.txt
# client: Node 20+
cd ../client && npm install
```

See `DEPLOYMENT.md` for standing up a local relay + agent + client for testing.

## Project Structure

See the repo layout in `README.md`. When adding a platform-specific agent
feature, keep OS-specific code isolated under `agent/linux/`, `agent/macos/`,
or `agent/windows/` — shared logic belongs in `agent/common/`.

## Making Changes

- **Protocol changes:** update `PROTOCOL.md` in the same PR as the code change. Protocol and implementation should never drift.
- **Security-relevant changes** (anything touching pairing, encryption, session auth, or agent privilege): flag this explicitly in the PR description. These get an extra review pass.
- **Tests:** new agent/relay logic should include tests; see `TESTING.md` for the current test strategy and what's covered vs. not yet.
- **Commit style:** clear, imperative commit messages (`Add macOS launchd packaging`, not `fixes`).

## Reporting Security Issues

**Do not open a public GitHub issue for a vulnerability.** Follow the process
in `SECURITY.md` instead.

## Code of Conduct

Be respectful, assume good faith, keep discussion focused on the technical
merits of a change. Maintainers reserve the right to close PRs/issues that
don't meet the ground rules above regardless of otherwise-good intentions —
this is a security-sensitive project and the bar for merging is "clearly
safe," not "probably fine."

## License

By contributing, you agree your contribution is licensed under the same
license as the component you're modifying (AGPL-3.0 for `relay-server/` and
`agent/`, MIT for `client/`) — see `LICENSE`.
