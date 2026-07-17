// termhop client — Screen 4: Terminal (compact-sheet variant, the chosen default)
//
// Real terminal rendering is xterm.js, mounted into `termRef`. This
// component owns the chrome (header, permission sheet, key row, input);
// wire xterm.js + the PROTOCOL.md pty_data/pty_input messages into
// useTerminalSession() (stubbed below) to make it live.
import React, { useEffect, useRef, useState } from 'react';
import { BackIcon, DotsIcon, LockIcon, ChevronDownIcon } from '../icons';

const COMPACT_KEYS = ['Ctrl', 'Esc', 'Tab', 'Home', 'End', 'PgUp', 'PgDn', '←', '↑', '↓', '→', '^C', '^D', '^Z'];

// Stand-in for the real hook that opens the encrypted WebSocket session,
// mounts xterm.js into `containerRef`, and streams pty_data/pty_input.
function useTerminalSession(containerRef, sessionId) {
  useEffect(() => {
    // Real implementation:
    //   const term = new Terminal({ fontFamily: 'var(--font-mono)', ... });
    //   term.open(containerRef.current);
    //   const ws = openEncryptedSession(sessionId);
    //   ws.onDecrypted(pty_data => term.write(pty_data));
    //   term.onData(input => ws.sendEncrypted({ type: 'pty_input', payload: input }));
    //   return () => { term.dispose(); ws.close(); };
  }, [sessionId]);
}

export default function TerminalScreen({ session, onBack, onOpenEncryptionInfo }) {
  const containerRef = useRef(null);
  useTerminalSession(containerRef, session?.id);

  // pending -> approved | denied
  const [permStatus, setPermStatus] = useState('pending');

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
        style={{ flex: 1, overflow: 'auto', padding: '12px 14px', fontFamily: 'var(--font-mono)', fontSize: 12, lineHeight: 1.6 }}
      >
        <TerminalPlaceholderContent />
        <button className="btn btn-secondary elev-sm" style={{ position: 'sticky', bottom: 8, left: '100%', fontSize: 11 }}>
          ↓ jump to bottom
        </button>
      </div>

      {/* Compact key row */}
      <div style={{ display: 'flex', gap: 6, padding: '8px 10px', borderTop: '1px solid var(--color-divider)', overflowX: 'auto' }}>
        {COMPACT_KEYS.map((k) => (
          <span key={k} className="tag tag-outline" style={{ fontFamily: 'var(--font-mono)', flex: 'none' }}>{k}</span>
        ))}
      </div>

      <div style={{ display: 'flex', gap: 8, padding: '10px 14px', borderTop: '2px solid var(--color-divider)' }}>
        <input className="input" style={{ fontFamily: 'var(--font-mono)' }} placeholder="Type a command…" />
      </div>

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
