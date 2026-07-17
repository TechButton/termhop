// termhop client — Screen 1: Pairing
import React, { useState } from 'react';

export default function PairingScreen({ agentHostname, onPaired }) {
  const [tab, setTab] = useState('qr'); // 'qr' | 'link'
  const [link, setLink] = useState('');
  // status: idle -> connecting -> handshaking -> paired | failed
  const [status, setStatus] = useState('idle');

  function startPair() {
    setStatus('connecting');
    // Real implementation: open wss:// to relay, present pairing token /
    // QR payload, then perform the ECDH handshake per PROTOCOL.md.
    // Timings below are placeholders standing in for that async flow.
    setTimeout(() => setStatus('handshaking'), 700);
    setTimeout(() => setStatus('paired'), 1500);
    setTimeout(() => onPaired?.(), 2300);
  }

  return (
    <div className="screen" style={{ padding: '20px 18px', gap: 16 }}>
      <h3>Pair with an agent</h3>
      <p style={{ margin: 0, fontSize: 12, opacity: .65 }}>
        This device will be able to run commands on <strong>{agentHostname}</strong>. No silent trust
        grants — you'll confirm every pairing.
      </p>

      <div className="seg" style={{ alignSelf: 'flex-start' }}>
        <label className="seg-opt"><input type="radio" name="pairtab" checked={tab === 'qr'} onChange={() => setTab('qr')} />Scan QR</label>
        <label className="seg-opt"><input type="radio" name="pairtab" checked={tab === 'link'} onChange={() => setTab('link')} />Paste link</label>
      </div>

      {tab === 'qr' && (
        <div style={{
          position: 'relative', width: '100%', aspectRatio: '1', background: 'var(--color-surface)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <span style={{ fontSize: 11, opacity: .5, letterSpacing: '.05em', textTransform: 'uppercase' }}>viewfinder</span>
          {['top:14px;left:14px;border-top:3px solid var(--color-accent);border-left:3px solid var(--color-accent)',
            'top:14px;right:14px;border-top:3px solid var(--color-accent);border-right:3px solid var(--color-accent)',
            'bottom:14px;left:14px;border-bottom:3px solid var(--color-accent);border-left:3px solid var(--color-accent)',
            'bottom:14px;right:14px;border-bottom:3px solid var(--color-accent);border-right:3px solid var(--color-accent)']
            .map((s, i) => (
              <div key={i} style={{ position: 'absolute', width: 22, height: 22, ...cssTextToObj(s) }} />
            ))}
        </div>
      )}

      {tab === 'link' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div className="field">
            <label>Pairing link</label>
            <input className="input" placeholder="termhop://pair/…" value={link} onChange={(e) => setLink(e.target.value)} />
          </div>
          <button className="btn btn-secondary btn-block">Paste from clipboard</button>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
        {status === 'idle' && <span style={{ opacity: .6 }}>Idle</span>}
        {status === 'connecting' && <span>Connecting…</span>}
        {status === 'handshaking' && <span>Handshaking… (ECDH)</span>}
        {status === 'paired' && <span style={{ color: 'var(--color-accent)' }}>Paired ✓</span>}
        {status === 'failed' && <span style={{ color: 'var(--color-accent)' }}>Failed — token expired</span>}
      </div>

      <div style={{ flex: 1 }} />

      {status === 'failed' && (
        <button className="btn btn-primary btn-block" onClick={() => setStatus('idle')}>Try again</button>
      )}
      {status === 'idle' && (
        <button className="btn btn-primary btn-block" onClick={startPair}>Pair device</button>
      )}
    </div>
  );
}

// Tiny helper so the QR corner-bracket styles above stay readable as data,
// not four hand-written style objects.
function cssTextToObj(cssText) {
  const out = {};
  cssText.split(';').forEach((decl) => {
    const [k, v] = decl.split(':');
    const camel = k.trim().replace(/-([a-z])/g, (_, c) => c.toUpperCase());
    out[camel] = v.trim();
  });
  return out;
}
