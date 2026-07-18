# Protocol v2 hosted cutover handoff

Status updated 2026-07-17 after the hosted protocol-v2 cutover. It supplements
`PROGRESS.md`; do not reconstruct the rollout from chat history.

## Cutover result

- Public source revision: `0dc7ab3` (`termhop`).
- Private source revision: `014e21a` (`termhop-control-plane`).
- The live relay runs protocol v2 and `/healthz` reports release `0dc7ab3`.
- The live control plane runs image revision `014e21a`.
- Nginx serves the hosted client from
  `/var/www/termhop-client-releases/0dc7ab3`.
- A disposable Linux agent/browser smoke test completed reviewed pairing, real
  encrypted PTY I/O, computed fingerprint display, agent termination,
  durable reconnection with fresh keys, replacement shell startup, and
  post-restart terminal I/O against the public deployment.
- Existing pre-v2 installed agents still require upgrade and re-pairing.
- `.playwright-mcp/` is pre-existing untracked user data; do not add, modify,
  or delete it.

Rollback assets are in
`/home/claude/backups/termhop-v2-cutover-20260718T0019Z` on the beta server.
The pre-v2 image tags are `termhop-relay-beta:pre-v2-f267581` and
`termhop-control-plane-app:pre-v2-2a213e7`; the original static directory
`/var/www/termhop-client` is unchanged.

## Verified locally

- Relay: 37 tests passed; Ruff and mypy passed.
- Agent: 41 tests passed, 5 OS-specific skips; Ruff and mypy passed.
- Client: 39 unit tests, 2 Playwright E2E tests, and production build passed.
- Hosted control plane: 31 tests passed, including all three Docker
  tenant-isolation tests; Ruff and mypy passed.
- npm production audit reported zero vulnerabilities.
- The Docker tenant-isolation tier was rerun with Docker-socket/group access.

## Required production configuration

Build the hosted static client with:

```bash
VITE_CONTROL_PLANE_URL=https://app.42oclock.com npm run build
```

The hosted control plane requires:

```dotenv
APP_BASE_URL=https://app.42oclock.com
CLIENT_BASE_URL=https://client.42oclock.com
CLIENT_HANDOFF_TTL_S=60
CLIENT_ACCESS_TTL_S=2592000
```

Set an immutable release identifier on every relay deployment:

```dotenv
PROTOCOL_VERSION=2
TERMHOP_RELEASE=<git-commit-or-release-id>
```

Self-hosted client builds deliberately leave `VITE_CONTROL_PLANE_URL` unset.

## Safe rollout order

This is a breaking coordinated protocol cutover. Do not replace only one live
component and leave it talking to an incompatible version.

1. Disconnect the current terminal session and establish independent SSH
   access to the server. Confirm a second recovery shell before changing
   services.
2. Review both worktrees, exclude `.playwright-mcp/`, commit each repository,
   and record both commit IDs.
3. Back up the control-plane database/configuration and current static client
   directory. Record the currently deployed container/image revisions.
4. Run the three Docker tenant-isolation tests with Docker group access.
   Completed locally on 2026-07-17: all three passed.
5. Build versioned relay and client artifacts without replacing live paths.
6. Deploy the control-plane changes and confirm existing login/dashboard flows.
7. Stage protocol-v2 relay instances and verify `/healthz` returns
   `protocol_version: 2` and the expected `release` value.
8. Publish the hosted client build configured for `app.42oclock.com`.
9. Upgrade/re-pair agents into v2. Existing pre-v2 agents are not compatible
   with the v2-only relay.
10. Exercise signup/login → client handoff → reviewed pairing → real terminal
    I/O → agent restart/reconnection before considering the cutover complete.

Use blue/green or parallel versioned endpoints where possible. Do not restart
the SSH daemon or remove the old relay/client artifacts during verification.

## Post-deploy checks

- `https://app.42oclock.com/` shows hosted and GitHub/self-hosted choices.
- Login followed by `/client` lands on `client.42oclock.com` without leaving a
  handoff token in the visible URL/history.
- `client.42oclock.com` fills the entire mobile and desktop viewport.
- Direct self-hosted pairing remains available in builds without the hosted
  environment variable.
- Pairing shows the real hostname for explicit confirmation.
- The encryption dialog displays a computed fingerprint.
- Terminal echo and resize work.
- Restarting the agent reconnects with fresh keys. Rebooting the computer
  starts a replacement shell; it does not claim the old PTY survived.
- Relay logs/Redis contain no terminal plaintext, pairing secret, durable
  device secret, or raw routing token.

The public relay/client and disposable-agent checks above passed. Still
required manually: authenticated existing-account login -> `/client` handoff
using real credentials, and upgrade/re-pair of each actual installed agent.

## Rollback boundary

Roll back relay, client, and agents together to the recorded pre-v2 revisions.
The control-plane homepage can roll back independently, but its client handoff
must not point users at an incompatible client build. Keep database backups and
old static assets until the full terminal/reconnection smoke test passes.

## Remaining release gates

- Independent security review of initial pairing and durable reconnection.
- Real macOS launchd and Windows Scheduled Task/ConPTY verification.
- Decide CSP/reverse-proxy headers for the hosted client, especially because
  browser site data contains a terminal-access credential. The deployed client
  currently returns no CSP or related hardening headers.
- Public repository finalized as `https://github.com/TechButton/termhop`.
