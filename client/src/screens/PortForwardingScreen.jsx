// termhop client — Screen 7: Port Forwarding
import React, { useState } from 'react';
import { BackIcon, LockIcon } from '../icons';

const ACTIVE_FORWARDS = [
  { port: 'localhost:3000', label: 'dev server' },
  { port: 'localhost:8080', label: 'api' },
];

export default function PortForwardingScreen({ onBack, onAddForward }) {
  const [port, setPort] = useState('');
  const [label, setLabel] = useState('');

  return (
    <div className="screen">
      <div className="screen-header">
        <button className="btn btn-icon" onClick={onBack} aria-label="Back"><BackIcon /></button>
        <h3>Port forwarding</h3>
        <span className="tag tag-outline" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <LockIcon />tunnel
        </span>
      </div>

      <div className="screen-body" style={{ gap: 8 }}>
        {ACTIVE_FORWARDS.map((f) => (
          <div key={f.port} className="card" style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, fontSize: 13 }}>{f.port}</div>
              <div style={{ fontSize: 11, opacity: .6 }}>{f.label}</div>
            </div>
            <span className="tag tag-accent">active</span>
            <button className="btn btn-ghost" style={{ fontSize: 12 }}>Open</button>
          </div>
        ))}

        <div className="hr" />

        <div className="field">
          <label>Port</label>
          <input className="input" placeholder="3000" value={port} onChange={(e) => setPort(e.target.value)} />
        </div>
        <div className="field">
          <label>Label (optional)</label>
          <input className="input" placeholder="dev server" value={label} onChange={(e) => setLabel(e.target.value)} />
        </div>
        <button
          className="btn btn-primary" style={{ justifyContent: 'center' }}
          onClick={() => { onAddForward({ port, label }); setPort(''); setLabel(''); }}
        >
          + Add forward
        </button>
      </div>
    </div>
  );
}
