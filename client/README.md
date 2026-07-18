# termhop client

Implements the 8 screens from `GUI_SPEC.md`, built from the "Modernist"
design system in the Claude Design handoff (`gui-specification-document/`).
This is real, editable source — not the prototype's templating markup —
translated 1:1 in structure and pixel values.

## Product decisions locked from the handoff review (2026-07-17)

- **Accent color:** `#cc6a2e` (burnt orange), set in `src/styles/tokens.css`.
- **Terminal permission prompt:** compact-sheet variant is the default
  (bottom sheet, not the inline card or fixed variant) — see
  `src/screens/TerminalScreen.jsx`.

## Structure

```
client/
├── index.html
├── package.json
├── src/
│   ├── main.jsx              # ReactDOM mount
│   ├── App.jsx                # screen router + shared dialog state
│   ├── styles/
│   │   ├── tokens.css          # design tokens (color ramps, type, spacing)
│   │   └── components.css      # .btn/.card/.field/.dialog/etc., built on tokens
│   ├── icons/index.jsx        # Lucide-style inline SVG icons
│   ├── components/
│   │   └── Dialogs.jsx         # Encryption info / regenerate key / unpair
│   └── screens/
│       ├── PairingScreen.jsx
│       ├── HomeScreen.jsx
│       ├── NewSessionScreen.jsx
│       ├── TerminalScreen.jsx
│       ├── NotificationScreen.jsx
│       ├── AgentStatusScreen.jsx
│       ├── PortForwardingScreen.jsx
│       └── SettingsScreen.jsx
```

## What's real vs. stubbed

- **Real:** full-viewport responsive landing/layout, optional hosted-login
  handoff, authenticated protocol-v2 pairing and saved-device reconnection,
  encrypted xterm.js I/O, terminal resize synchronization, virtual keys,
  agent card expand/collapse, sort toggles, form fields, and dialogs.
- **Stubbed, clearly marked in comments:**
  - `PairingScreen` — paste-link pairing is real; camera QR scanning is not.
  - `HomeScreen` — session lists are hardcoded fixtures. Replace with the
    live `session_list` message from the agent (see `PROTOCOL.md`).
  - `AgentStatusScreen` — same, hardcoded agent fixtures.
  - Dialog confirm handlers (`onConfirm` for regenerate/unpair) are no-ops
    with `TODO` comments — wire to the real relay calls once the relay
    server exists.

## Running locally

```bash
cd client
npm install
npm run dev
```

Direct pairing works without an account. To link an operator's optional account
site, copy `.env.example` and set `VITE_CONTROL_PLANE_URL`. The account site
redirects back with a one-minute single-use `#handoff` code; the client POSTs
it to `/api/client/exchange`, clears it from browser history immediately, and
receives account/relay metadata plus a revocable scoped access token. Endpoint
device secrets stay in browser site data and never enter this exchange.

## Not yet done

- Capacitor wrapper for push notifications and home-screen install
  (per `PROJECT_PLAN.md` build order, this comes after the web client is
  validated on its own).
- Multi-PTY session management and live data for the fixture-driven management
  screens. Durable device reconnection is implemented, but an OS reboot starts
  a replacement shell because no process can survive an OS reboot.
