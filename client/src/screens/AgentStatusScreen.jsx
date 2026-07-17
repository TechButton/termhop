// termhop client — Screen 6: Agent / Connection Status
import React, { useState } from 'react';
import { BackIcon, LaptopIcon, LockIcon } from '../icons';

const INITIAL_AGENTS = [
  { name: 'workstation-01', os: 'macOS', lastSeen: 'now', relay: 'relay.termhop.dev:443', online: true },
  { name: 'build-server', os: 'Linux', lastSeen: '3h ago', relay: 'relay.termhop.dev:443', online: false },
  { name: 'gaming-pc', os: 'Windows', lastSeen: 'now', relay: 'relay.termhop.dev:443', online: true },
];

export default function AgentStatusScreen({ onBack, onAddAgent, onRequestUnpair }) {
  const [agents, setAgents] = useState(INITIAL_AGENTS.map((a) => ({ ...a, expanded: false })));

  function toggle(name) {
    setAgents((list) => list.map((a) => (a.name === name ? { ...a, expanded: !a.expanded } : a)));
  }

  return (
    <div className="screen">
      <div className="screen-header">
        <button className="btn btn-icon" onClick={onBack} aria-label="Back"><BackIcon /></button>
        <h3>Agents</h3>
      </div>

      <div className="screen-body" style={{ gap: 10 }}>
        {agents.map((a) => (
          <div key={a.name} className="card" style={{ gap: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }} onClick={() => toggle(a.name)}>
              <span style={{ opacity: .7 }}><LaptopIcon /></span>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, fontSize: 13 }}>{a.name}</div>
                <div style={{ fontSize: 11, opacity: .6 }}>{a.os} · {a.lastSeen}</div>
              </div>
              <span className={`status-dot status-dot--${a.online ? 'live' : 'offline'}`} />
            </div>

            {a.expanded && (
              <div style={{ borderTop: '1px solid var(--color-divider)', paddingTop: 8, fontSize: 12, display: 'flex', flexDirection: 'column', gap: 6 }}>
                <div>Relay: <code>{a.relay}</code></div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}><LockIcon />Encrypted session established</div>
                {!a.online && (
                  <div className="tag tag-outline" style={{ alignSelf: 'flex-start' }}>
                    Agent offline — check the PC, not your network
                  </div>
                )}
                <button
                  className="btn btn-secondary" style={{ alignSelf: 'flex-start', fontSize: 12, color: 'var(--color-accent)' }}
                  onClick={() => onRequestUnpair(a.name)}
                >
                  Unpair
                </button>
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="screen-footer">
        <button className="btn btn-secondary btn-block" style={{ justifyContent: 'center' }} onClick={onAddAgent}>
          + Add another agent
        </button>
      </div>
    </div>
  );
}
