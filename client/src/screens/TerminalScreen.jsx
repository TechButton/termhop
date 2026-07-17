// termhop client — Screen 4: Terminal (compact-sheet variant, the chosen default)
//
// Real terminal rendering is xterm.js, mounted into `containerRef` by
// useTerminalSession(), which pumps encrypted pty_data/pty_input over the
// RelayClient established during pairing (see PairingScreen.jsx).
import React, { useEffect, useRef, useState } from 'react';
import { Terminal } from '@xterm/xterm';
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

    const term = new Terminal({ fontFamily: 'var(--font-mono)', fontSize: 12, convertEol: true });
    term.open(containerRef.current);

    relayClient.beginStreaming({
      onEncrypted: (plaintext) => term.write(new TextDecoder().decode(plaintext)),
      onSessionClose: () => term.write('\r\n\x1b[2m[session closed]\x1b[0m\r\n'),
      onError: (payload) => term.write(`\r\n\x1b[2m[relay error: ${payload?.message ?? 'unknown'}]\x1b[0m\r\n`),
    });

    const inputListener = term.onData((input) => {
      relayClient.sendEncrypted('pty_input', new TextEncoder().encode(input));
    });

    return () => {
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
        style={{ flex: 1, overflow: 'auto', padding: relayClient ? 0 : '12px 14px', fontFamily: 'var(--font-mono)', fontSize: 12, lineHeight: 1.6 }}
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
              fontFamily: 'var(--font-mono)', flex: 'none', cursor: 'pointer', border: 0,
              background: k.kind === 'modifier' && ctrlArmed ? 'var(--color-accent)' : undefined,
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
