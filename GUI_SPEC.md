# GUI_SPEC.md — termhop Client

Covers every screen the client (`client/`) needs, based on the feature set in
PROJECT_PLAN.md and PROTOCOL.md. Written screen-first so it can drive both a
Claude Design mockup pass and eventual component build-out.

## Design Constraints

- Mobile-first (Capacitor-wrapped), but must degrade gracefully to a plain desktop browser tab.
- The app shell and active screen always fill the complete dynamic viewport at any window size. Desktop may use the extra space, but must not strand the app in a partial-height or half-width phone frame unless an explicit device-preview mode is being shown.
- Terminal view is the core screen — everything else exists to get the user into or between terminal sessions fast.
- Must show encryption/security state clearly — this is a tool people trust with shell access, the UI should never leave that ambiguous.
- Dark theme by default (matches terminal conventions and your existing Frequency 42 LLC teal/near-black brand direction).

## Screens

### 0. Public / Account Landing
**Purpose:** Link the optional hosted account site to the terminal client while
keeping direct self-hosted pairing available.
- Full-viewport responsive hero matching the Modernist token system.
- Hosted builds show Log in / Account links and account relay status.
- Self-hosted builds (no `VITE_CONTROL_PLANE_URL`) show direct pairing only.
- Locally saved computers appear with reconnect status. A dropped device
  connection retries for up to one minute after a reboot.

### 1. Pairing Screen
**Purpose:** First-run and re-pairing to a new agent.
- Two entry modes, tabbed or toggled: **Scan QR** / **Paste link**.
- Camera viewfinder for QR mode with a scan-target overlay.
- Text field + paste button for link mode.
- Status states: `Idle` → `Connecting…` → `Handshaking…` (ECDH in progress) → `Paired ✓` or `Failed — reason`.
- Explicit microcopy confirming what pairing does: "This device will be able to run commands on `<agent hostname>`." — no silent trust grants.

### 2. Session List (Home)
**Purpose:** Landing screen after pairing — shows what's running.
- Two grouped sections: **Live Processes** and **Resumable Sessions**.
- Each row: icon (by process type — claude.exe, codex, cmd, bash, generic), title (cwd or session name), subtitle (last activity / "2m ago"), status dot (live/idle/waiting-for-input).
- Sort control (Newest / Oldest / Alphabetical).
- Prominent **+ New Session** action (opens Screen 3).
- Pull-to-refresh.
- Empty state: no agent processes found — link to Screen 6 (agent status) to check connectivity.

### 3. New Session Launcher
**Purpose:** Start a fresh terminal/CLI tool from the phone.
- Shell picker: Claude Code / Codex CLI / Aider / cmd.exe / PowerShell / bash / "Any CLI" (custom command field).
- Working directory field (with recent-dirs suggestions from agent).
- Two toggles, both **off by default**: `Skip permissions` and `Strict input` — per CONTRIBUTING.md ground rule 3, auto-accept must never default on, and this screen is where that's enforced visually (e.g. a small warning icon appears next to Skip Permissions when toggled on).
- Launch button → transitions into Screen 4 for the new session.

### 4. Terminal View (core screen)
**Purpose:** Live terminal, the primary interaction surface.
- Full-bleed xterm.js render area.
- Top bar: session title/cwd, live status indicator, connection/encryption badge (small lock icon — tap for details), overflow menu (rename, close, resize hints).
- Bottom input row: text field or direct-to-terminal typing, plus a **virtual key row**: `Ctrl` `Esc` `Tab` `Home` `End` arrows `^C` `^D` `^Z` — collapsible to save vertical space.
- Inline **permission prompts**: when the agent surfaces a "Make this edit? Y/n"-style pattern, render it as a distinct card (not just raw text) with tappable Yes / Yes-don't-ask-again / No buttons, mirroring what the CLI itself offers — this is the single most important interaction to get right, per the reference product's own UI.
- Auto-scroll with a "jump to bottom" affordance when scrolled up.
- Landscape mode: wider virtual keyboard row, same layout otherwise.

### 5. Idle/Notification Detail
**Purpose:** What happens when a push notification is tapped.
- Deep-links directly into Screen 4 for the relevant session, scrolled to the point that triggered the alert.
- Notification itself (OS-level) stays generic per SECURITY.md — no terminal content in the push body, just "Session waiting for input" + session nickname.

### 6. Agent / Connection Status
**Purpose:** Diagnose connectivity, manage paired agents.
- List of paired agents (multiple PCs supported): name, OS icon (Linux/macOS/Windows), online/offline, last-seen.
- Per-agent detail: relay URL in use, encryption status, "Unpair" action (destructive, confirm dialog).
- Add another agent → back to Screen 1.

### 7. Port Forwarding
**Purpose:** Access a dev server running on the agent machine.
- List of active forwards: local port → status → open-in-browser button.
- + Add Forward: port number input, optional label.
- Encrypted-tunnel badge, same visual language as Screen 4's lock icon.

### 8. Settings
**Purpose:** App-level preferences, not session-specific.
- Notification preferences (idle alert timing threshold, sound/vibration).
- Theme (dark default / light / system).
- Default shell for New Session.
- Security section: view long-term device key fingerprint (for out-of-band verification against the agent), option to regenerate.
- About / version / link to SECURITY.md and license info.

## Shared Components

- **Status dot** (live=green, idle=amber, waiting-for-input=red-pulse, offline=gray) — reused across Screens 2, 4, 6.
- **Encryption badge** — reused Screens 4, 7; tapping always shows the same detail sheet (cipher, session key fingerprint, "relay cannot read this" explainer line).
- **Virtual key row** — Screen 4 primarily, reusable if a second terminal-like surface is ever added.
- **Permission-prompt card** — Screen 4; should visually match across all shell types even though the underlying CLI's prompt format differs (Claude Code vs. Codex vs. a raw `y/n` bash script).

## States to Design For (don't skip these in the mockup pass)

- Disconnected / reconnecting (relay unreachable) — banner, not a full-screen blocker, since session state should persist locally while reconnecting.
- Agent offline vs. relay offline — these need visually distinct messaging since the fix differs (check the PC vs. check your own network).
- Pairing token expired mid-scan.
- Session ended by the agent side (process exited) vs. closed by the user.

## Suggested Next Step

Take this spec into Claude Design to produce actual visual mockups for
Screens 1–4 first (pairing → home → new session → terminal), since those are
the critical path a new user hits in their first 60 seconds. Screens 5–8 can
follow once the core flow is validated.
