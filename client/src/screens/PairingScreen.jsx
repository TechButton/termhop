// termhop client — Screen 1: Pairing
import React, { useState } from 'react';
import { RelayClient, HandshakeError } from '../lib/relayClient';
import { decodePairingLink, PairingLinkError } from '../lib/pairingLink';

export default function PairingScreen({ agentHostname, onPaired }) {
  const [tab, setTab] = useState('qr'); // 'qr' | 'link'
  const [link, setLink] = useState('');
  // status: idle -> connecting -> handshaking -> paired | failed
  const [status, setStatus] = useState('idle');
  const [failureReason, setFailureReason] = useState('');
  const [hostname, setHostname] = useState(agentHostname);

  async function startPair() {
    let parsed;
    try {
      parsed = decodePairingLink(link);
    } catch (err) {
      setFailureReason(err instanceof PairingLinkError ? err.message : 'invalid pairing link');
      setStatus('failed');
      return;
    }
    if (parsed.hostname) setHostname(parsed.hostname);

    const client = new RelayClient(parsed.relayUrl);
    setStatus('connecting');
    try {
      await client.connect();
      setStatus('handshaking');
      await client.sendPairRequest(parsed.token);
      const { sessionId, agentHostname: challengeHostname } = await client.awaitPairChallengeAndDeriveKey();
      if (challengeHostname) setHostname(challengeHostname);
      client.sendPairComplete();
      setStatus('paired');
      onPaired?.({ client, sessionId, agentHostname: challengeHostname || parsed.hostname });
    } catch (err) {
      setFailureReason(err instanceof HandshakeError ? err.message : 'connection failed');
      setStatus('failed');
      client.close();
    }
  }

  return (
    <div className="screen" style={{ padding: '20px 18px', gap: 16 }}>
      <h3>Pair with an agent</h3>
      <p style={{ margin: 0, fontSize: 12, opacity: .65 }}>
        This device will be able to run commands on <strong>{hostname}</strong>. No silent trust
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
          <span style={{ fontSize: 11, opacity: .5, letterSpacing: '.05em', textTransform: 'uppercase' }}>
            camera QR scanning not yet implemented — use "Paste link"
          </span>
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
            <input
              className="input"
              placeholder="termhop://pair?relay=…&token=…"
              value={link}
              onChange={(e) => setLink(e.target.value)}
            />
          </div>
          <button
            className="btn btn-secondary btn-block"
            onClick={async () => {
              try {
                const text = await navigator.clipboard.readText();
                setLink(text);
              } catch {
                /* clipboard access denied/unavailable — user can paste manually */
              }
            }}
          >
            Paste from clipboard
          </button>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
        {status === 'idle' && <span style={{ opacity: .6 }}>Idle</span>}
        {status === 'connecting' && <span>Connecting…</span>}
        {status === 'handshaking' && <span>Handshaking… (ECDH)</span>}
        {status === 'paired' && <span style={{ color: 'var(--color-accent)' }}>Paired ✓</span>}
        {status === 'failed' && <span style={{ color: 'var(--color-accent)' }}>Failed — {failureReason || 'unknown error'}</span>}
      </div>

      <div style={{ flex: 1 }} />

      {status === 'failed' && (
        <button className="btn btn-primary btn-block" onClick={() => setStatus('idle')}>Try again</button>
      )}
      {status === 'idle' && (
        <button className="btn btn-primary btn-block" onClick={startPair} disabled={tab === 'link' && !link}>
          Pair device
        </button>
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
