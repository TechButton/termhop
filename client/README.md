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

- **Real:** all layout, styling, component states (pairing status machine,
  agent card expand/collapse, sort toggles, form fields, all three dialogs).
- **Stubbed, clearly marked in comments:**
  - `PairingScreen` — `startPair()` fakes the connecting → handshaking →
    paired timeline with `setTimeout`. Replace with the real relay
    WebSocket + ECDH handshake per `PROTOCOL.md`.
  - `TerminalScreen` — `useTerminalSession()` is an empty hook with the
    real xterm.js + encrypted pty_data/pty_input wiring commented in as
    a guide. `xterm` is already a declared dependency.
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

## Not yet done

- xterm.js mount + real terminal I/O (see stub above).
- Capacitor wrapper for push notifications and home-screen install
  (per `PROJECT_PLAN.md` build order, this comes after the web client is
  validated on its own).
- Virtual key row is currently static (compact 13-key set); wiring key
  presses to actual terminal input (Ctrl-combos, arrows) is part of the
  xterm.js integration.
- Responsive/desktop-browser layout — screens are currently sized for
  the phone frame only, per the prototype.
