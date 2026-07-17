// termhop client — Screen 4: Terminal (compact-sheet variant, the chosen default)
//
// Real terminal rendering is xterm.js, mounted into `containerRef` by
// useTerminalSession(), which pumps encrypted pty_data/pty_input over the
// RelayClient established during pairing (see PairingScreen.jsx).
import React, { useEffect, useRef, useState } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
// REQUIRED — xterm.js ships this stylesheet to hide/position its internal
// helper elements (the accessibility live-region row mirror, the keyboard-
// input helper textarea, the cursor layer). Without it those elements
// render visibly, unstyled, overlapping the real terminal content — this
// was the actual cause of the garbled repeated-character row that showed
// up at the top of every real session; several other theories (resize
// timing, font loading) were ruled out by direct DOM inspection before
// finding this was simply a missing required import.
import '@xterm/xterm/css/xterm.css';
import { BackIcon, DotsIcon, LockIcon, ChevronDownIcon } from '../icons';

const COMPACT_KEYS = [
  { label: 'Ctrl', kind: 'modifier' },
  { label: 'Esc', bytes: '\x1b' },
  { label: 'Tab', bytes: '\t' },
  { label: 'Home', bytes: '\x1b[H' },
  { label: 'End', bytes: '\x1b[F' },
  { label: 'PgUp', bytes: '\x1b[5~' },
  { label: 'PgDn', bytes: '\x1b[6~' },
  { label: '←', bytes: '\x1b[D' },
  { label: '↑', bytes: '\x1b[A' },
  { label: '↓', bytes: '\x1b[B' },
  { label: '→', bytes: '\x1b[C' },
  { label: '^C', bytes: '\x03' },
  { label: '^D', bytes: '\x04' },
  { label: '^Z', bytes: '\x1a' },
];

// Mounts a real xterm.js Terminal and pumps it over the RelayClient that
// PairingScreen already connected and paired — this must be the SAME
// connection, not a new one (the relay ties a session to one live
// WebSocket; reconnecting means re-pairing from scratch, not resuming).
function useTerminalSession(containerRef, relayClient) {
  useEffect(() => {
    if (!containerRef.current || !relayClient) return undefined;

    // xterm.js renders to a <canvas>, and canvas 2D font/color strings
    // don't resolve CSS custom properties the way stylesheet values do —
    // passing 'var(--font-mono)'/'var(--color-surface)' directly silently
    // falls back to xterm's own defaults (a plain sans-serif font and a
    // white background), which is exactly the "white parts don't match"
    // mismatch against the app's dark theme. Resolve the actual computed
    // values once at mount instead.
    const styles = getComputedStyle(document.documentElement);
    const resolve = (name, fallback) => styles.getPropertyValue(name).trim() || fallback;

    const term = new Terminal({
      fontFamily: resolve('--font-mono', 'monospace'),
      fontSize: 12,
      convertEol: true,
      theme: {
        background: resolve('--color-neutral-900', '#1a1a1a'),
        foreground: resolve('--color-neutral-100', '#f0f0f0'),
        cursor: resolve('--color-accent', '#cc6a2e'),
        selectionBackground: resolve('--color-accent-300', '#7a4a2a'),
      },
    });
    // xterm.js otherwise renders at a fixed default size (80x24 cells)
    // regardless of its container's actual size — the FitAddon is what
    // makes the canvas actually fill containerRef, instead of leaving the
    // container's own (unstyled) background showing around a
    // fixed-size terminal.
    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.open(containerRef.current);
    fitAddon.fit();

    const resizeObserver = new ResizeObserver(() => fitAddon.fit());
    resizeObserver.observe(containerRef.current);

    relayClient.beginStreaming({
      onEncrypted: (plaintext) => term.write(new TextDecoder().decode(plaintext)),
      onSessionClose: () => term.write('\r\n\x1b[2m[session closed]\x1b[0m\r\n'),
      onError: (payload) => term.write(`\r\n\x1b[2m[relay error: ${payload?.message ?? 'unknown'}]\x1b[0m\r\n`),
    });

    const inputListener = term.onData((input) => {
      relayClient.sendEncrypted('pty_input', new TextEncoder().encode(input));
    });

    return () => {
      resizeObserver.disconnect();
      inputListener.dispose();
      term.dispose();
      // Deliberately NOT closing relayClient here — closing the one shared
      // WebSocket on unmount would kill the session; that only happens from
      // an explicit disconnect/unpair action.
    };
  }, [containerRef, relayClient]);
}

export default function TerminalScreen({ session, relayClient, onBack, onOpenEncryptionInfo }) {
  const containerRef = useRef(null);
  useTerminalSession(containerRef, relayClient);

  const [ctrlArmed, setCtrlArmed] = useState(false);

  function sendKey(key) {
    if (!relayClient) return;
    if (key.kind === 'modifier') {
      setCtrlArmed((armed) => !armed);
      return;
    }
    let bytes = key.bytes;
    if (ctrlArmed && bytes.length === 1) {
      // Ctrl+<letter> -> control byte (Ctrl+A=0x01 .. Ctrl+Z=0x1a).
      bytes = String.fromCharCode(bytes.toUpperCase().charCodeAt(0) & 0x1f);
    }
    relayClient.sendEncrypted('pty_input', new TextEncoder().encode(bytes));
    setCtrlArmed(false);
  }

  // No real idle/permission-prompt detection exists yet (PROJECT_PLAN.md
  // step 6) — default to no prompt so the real terminal isn't blocked by
  // the demo fixture below on every real session.
  const [permStatus, setPermStatus] = useState('approved');

  return (
    <div className="screen" style={{ position: 'relative' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '12px 14px', borderBottom: '2px solid var(--color-divider)' }}>
        <button className="btn btn-icon" onClick={onBack} aria-label="Back"><BackIcon /></button>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 600, fontSize: 13 }}>{session?.title ?? 'termhop-client — main'}</div>
          <div style={{ fontSize: 10, opacity: .6, display: 'flex', alignItems: 'center', gap: 5 }}>
            <span className="status-dot status-dot--live" style={{ width: 6, height: 6 }} />live
          </div>
        </div>
        <button className="btn btn-icon" onClick={onOpenEncryptionInfo} aria-label="Encryption status"><LockIcon /></button>
        <button className="btn btn-icon" aria-label="More"><DotsIcon /></button>
      </div>

      {/* xterm.js mounts here */}
      <div
        ref={containerRef}
        style={{
          flex: 1, overflow: 'auto', padding: relayClient ? 0 : '12px 14px',
          fontFamily: 'var(--font-mono)', fontSize: 12, lineHeight: 1.6,
          background: relayClient ? 'var(--color-neutral-900)' : undefined,
        }}
      >
        {!relayClient && <TerminalPlaceholderContent />}
        {!relayClient && (
          <button className="btn btn-secondary elev-sm" style={{ position: 'sticky', bottom: 8, left: '100%', fontSize: 11 }}>
            ↓ jump to bottom
          </button>
        )}
      </div>

      {/* Compact key row */}
      <div style={{ display: 'flex', gap: 6, padding: '8px 10px', borderTop: '1px solid var(--color-divider)', overflowX: 'auto' }}>
        {COMPACT_KEYS.map((k) => (
          <button
            key={k.label}
            type="button"
            className="tag tag-outline"
            style={{
              // .tag-outline was written for a <span> (transparent by
              // default) — a native <button> has its own browser-default
              // background (usually a light "buttonface" color) that the
              // class never overrides, which combined with the dark
              // theme's light --color-text produced white text on a
              // white box. Explicit 'transparent' here is the fix.
              fontFamily: 'var(--font-mono)', flex: 'none', cursor: 'pointer',
              background: k.kind === 'modifier' && ctrlArmed ? 'var(--color-accent)' : 'transparent',
              color: k.kind === 'modifier' && ctrlArmed ? 'var(--color-neutral-900)' : 'var(--color-text)',
            }}
            onClick={() => sendKey(k)}
          >
            {k.label}
          </button>
        ))}
      </div>

      {/* Plain-text input row — mainly so mobile browsers get a keyboard
          affordance; xterm.js itself captures direct typing when its
          hidden textarea has focus, this is a fallback/convenience path
          that sends a full line + newline on submit. */}
      <form
        style={{ display: 'flex', gap: 8, padding: '10px 14px', borderTop: '2px solid var(--color-divider)' }}
        onSubmit={(e) => {
          e.preventDefault();
          const input = e.currentTarget.elements.namedItem('cmd');
          if (relayClient && input.value) {
            relayClient.sendEncrypted('pty_input', new TextEncoder().encode(input.value + '\n'));
            input.value = '';
          }
        }}
      >
        <input name="cmd" className="input" style={{ fontFamily: 'var(--font-mono)' }} placeholder="Type a command…" />
      </form>

      {/* Compact-sheet permission prompt — bottom sheet instead of inline card */}
      {permStatus === 'pending' && (
        <div className="sheet-backdrop">
          <div className="sheet">
            <div className="card-kicker">Permission requested</div>
            <p className="card-body">Claude wants to edit <code>client/src/App.tsx</code>.</p>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button className="btn btn-primary" style={{ fontSize: 12 }} onClick={() => setPermStatus('approved')}>Yes</button>
              <button className="btn btn-secondary" style={{ fontSize: 12 }} onClick={() => setPermStatus('approved')}>Don't ask again</button>
              <button className="btn btn-secondary" style={{ fontSize: 12 }} onClick={() => setPermStatus('denied')}>No</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function TerminalPlaceholderContent() {
  // Placeholder scrollback shown before xterm.js is wired in — remove once
  // the real pty_data stream is live.
  return (
    <>
      <div style={{ opacity: .8 }}>$ npm run build</div>
      <div style={{ opacity: .6 }}>webpack compiled successfully in 2.1s</div>
      <div style={{ opacity: .8 }}>$ claude</div>
      <div style={{ opacity: .6 }}>Reading client/src/App.tsx…</div>
      <div style={{ opacity: .6 }}>Found 1 issue in terminal scroll handling.</div>
    </>
  );
}
