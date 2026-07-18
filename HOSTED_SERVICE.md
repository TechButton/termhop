# Hosted service boundary

termhop is self-hostable first. The relay, agents, browser client, encryption
protocol, saved-device reconnection, and normal management features belong in
this public repository.

An optional paid service can charge for operations rather than artificial
feature removal: isolated managed relays, TLS and upgrades, monitoring and an
uptime target, push delivery, encrypted device-authorization recovery, team
approval/audit metadata, managed agent rollout, and support. Terminal content
and endpoint private credentials must remain unavailable to the operator.

The reference client enables a hosted account link only when its builder sets:

```dotenv
VITE_CONTROL_PLANE_URL=https://accounts.example.com
```

When unset, the landing page shows self-hosted mode and direct pairing. A
compatible account service may redirect to
`https://client.example/#handoff=<single-use-code>` and implement the exchange
contract documented in `client/README.md`. This adapter does not alter the wire
protocol or make a self-hosted relay contact Frequency 42 infrastructure.
