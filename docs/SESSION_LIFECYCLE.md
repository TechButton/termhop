# Persistent session lifecycle

TermHop separates the long-lived agent from the browser tab. A browser may
detach, close, or reconnect without destroying the agent's persistent session.

## States

`created` → `running` → `detached` → `running` → `exited`

An operator may also move a running or detached session to `paused`, then
resume it, or terminate it. `terminated` is terminal. State is persisted in a
per-user manifest under the platform's normal application state directory;
the file is created with owner-only permissions and written atomically.

## Labels and control

Each session has a bounded human-readable label, working directory, creation
time, last-seen time, and optional exit code. Labels are metadata only and are
never interpreted as shell input. A controller lease is issued for a short
period and only one browser may hold it at a time. A second browser can see
metadata but must wait for the lease to expire or be released before sending
terminal input.

## Wire behavior

After pairing or resume, the agent sends a `session_list` message containing
bounded metadata for the sessions it owns. The relay checks the authenticated
role and forwards this message to the paired browser without decrypting or
persisting terminal output. Browser-originated `session_list` messages are
rejected. Terminal bytes remain in the existing encrypted `pty_data`/
`pty_input` envelopes.

## Operational guidance

Use a descriptive label when starting a session:

```sh
termhop-agent pair --relay wss://relay.example.com --label "overnight build"
```

The agent itself remains the authority for process state. The relay and browser
should treat metadata as a view and refresh it after reconnecting; neither can
claim that a process is running without the agent reporting it.
