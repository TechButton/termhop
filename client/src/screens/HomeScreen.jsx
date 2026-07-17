// termhop client — Screen 2: Home / Session List
import React, { useState } from 'react';
import { DotsIcon } from '../icons';

const LIVE_SESSIONS = [
  { id: 's1', badge: 'C', badgeStyle: 'accent', cwd: '~/projects/termhop-client', meta: 'claude.exe · running · 3m', dot: 'live' },
  { id: 's2', badge: '$', badgeStyle: 'mono', cwd: '~/scripts/deploy.sh', meta: 'bash · waiting for input · 12s', dot: 'waiting' },
];
const RESUMABLE_SESSIONS = [
  { id: 's3', badge: 'Cx', badgeStyle: 'mono-sm', cwd: '~/api/server', meta: 'codex · idle · 2h ago', dot: 'idle' },
  { id: 's4', badge: '>_', badgeStyle: 'mono-sm', cwd: 'C:\\Users\\dev\\build', meta: 'cmd.exe · idle · 1d ago', dot: 'idle' },
];

function SessionCard({ session, onOpen }) {
  return (
    <div
      className="card"
      style={{ cursor: 'pointer', flexDirection: 'row', alignItems: 'center', gap: 12 }}
      onClick={onOpen}
    >
      <div style={{
        width: 34, height: 34, flex: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: session.badgeStyle === 'accent' ? 'var(--color-accent-800)' : 'var(--color-neutral-700)',
        color: session.badgeStyle === 'accent' ? 'var(--color-accent-200)' : 'var(--color-neutral-100)',
        font: session.badgeStyle === 'accent' ? '600 12px var(--font-heading)' : '600 12px var(--font-mono)',
      }}>
        {session.badge}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 600, fontSize: 13 }}>{session.cwd}</div>
        <div style={{ fontSize: 11, opacity: .6 }}>{session.meta}</div>
      </div>
      <span className={`status-dot status-dot--${session.dot}`} />
    </div>
  );
}

export default function HomeScreen({ onOpenSession, onNewSession, onSettings, onAgents, onPorts, onNotificationDemo }) {
  const [sort, setSort] = useState('newest'); // newest | oldest | alpha

  return (
    <div className="screen">
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '16px 18px 8px', borderBottom: '2px solid var(--color-divider)' }}>
        <h3 style={{ margin: 0, flex: 1 }}>termhop</h3>
        <button className="btn btn-icon" onClick={onSettings} aria-label="Settings"><DotsIcon /></button>
      </div>
      <div style={{ padding: '10px 18px 0', fontSize: 11, opacity: .5, textAlign: 'center' }}>↓ pull to refresh</div>
      <div style={{ padding: '10px 18px' }}>
        <div className="seg">
          <label className="seg-opt"><input type="radio" name="sort" checked={sort === 'newest'} onChange={() => setSort('newest')} />Newest</label>
          <label className="seg-opt"><input type="radio" name="sort" checked={sort === 'oldest'} onChange={() => setSort('oldest')} />Oldest</label>
          <label className="seg-opt"><input type="radio" name="sort" checked={sort === 'alpha'} onChange={() => setSort('alpha')} />A–Z</label>
        </div>
      </div>

      <div style={{ padding: '0 18px' }}>
        <h6 style={{ marginBottom: 8 }}>Live Processes</h6>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {LIVE_SESSIONS.length === 0 ? (
            <EmptyState text="No live sessions. Start one below." />
          ) : LIVE_SESSIONS.map((s) => <SessionCard key={s.id} session={s} onOpen={() => onOpenSession(s.id)} />)}
        </div>
      </div>

      <div style={{ padding: '16px 18px 0' }}>
        <h6 style={{ marginBottom: 8 }}>Resumable Sessions</h6>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {RESUMABLE_SESSIONS.map((s) => <SessionCard key={s.id} session={s} onOpen={() => onOpenSession(s.id)} />)}
        </div>
      </div>

      <div style={{ flex: 1 }} />
      <div style={{ padding: '14px 18px', borderTop: '2px solid var(--color-divider)', display: 'flex', gap: 8 }}>
        <button className="btn btn-primary" style={{ flex: 1, justifyContent: 'center' }} onClick={onNewSession}>+ New Session</button>
      </div>
      <div style={{ display: 'flex', borderTop: '1px solid var(--color-divider)' }}>
        <button className="btn" style={{ flex: 1, justifyContent: 'center', borderRadius: 0, fontSize: 11 }} onClick={onAgents}>Agents</button>
        <button className="btn" style={{ flex: 1, justifyContent: 'center', borderRadius: 0, fontSize: 11 }} onClick={onPorts}>Ports</button>
        <button className="btn" style={{ flex: 1, justifyContent: 'center', borderRadius: 0, fontSize: 11 }} onClick={onNotificationDemo}>Notif. demo</button>
      </div>
    </div>
  );
}

function EmptyState({ text }) {
  return <p style={{ margin: 0, fontSize: 12, opacity: .55 }}>{text}</p>;
}
