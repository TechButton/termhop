# Release checklist

Before the consolidated public release:

Install the pinned agent/relay dependencies in isolated environments first,
then run:

```sh
PYTHONPATH=agent pytest -q agent/tests
PYTHONPATH=relay-server pytest -q relay-server/tests
```

The browser verification is:

```sh
cd ../termhop-control-plane/client
npm test -- --run
npm run build
```

- Run agent tests with the pinned virtualenv dependencies.
- Run relay tests with FastAPI, Redis, and the pinned production requirements.
- Run the private client test suite and production build.
- Review installer behavior on Linux, macOS, and Windows, including clean
  install, update, missing `venv`, and non-admin startup.
- Confirm QR pairing, URL fallback, saved-device resume, and clean Ctrl+C.
- Confirm session metadata is agent-originated and browser-originated
  `session_list` messages are rejected.
- Confirm session labels, pause/resume, detach/reconnect, lease expiry, and
  process exit behavior.
- Review Docker resource limits, TLS termination, Redis exposure, and demo
  command allowlists.
- Commit the public agent/relay/docs changes as one release commit only after
  all checks pass; push that commit once.
- Push the matching private client/control-plane release and record the exact
  public/private commit pair in the release notes.
