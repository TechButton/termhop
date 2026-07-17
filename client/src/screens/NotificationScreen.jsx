// termhop client — Screen 5: Notification Detail
import React from 'react';
import { BellIcon } from '../icons';

export default function NotificationScreen({ onOpenTerminal }) {
  return (
    <div className="screen" style={{ padding: 18, gap: 14 }}>
      <h3>Push notification</h3>
      <p style={{ margin: 0, fontSize: 12, opacity: .6 }}>
        OS-level banner — no terminal content shown, per SECURITY.md.
      </p>
      <div
        className="card elev-md"
        style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 10, cursor: 'pointer' }}
        onClick={onOpenTerminal}
      >
        <div style={{
          width: 28, height: 28, flex: 'none', background: 'var(--color-accent)', color: 'var(--color-bg)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <BellIcon />
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <strong style={{ fontSize: 12 }}>termhop</strong>
            <span style={{ fontSize: 10, opacity: .5 }}>now</span>
          </div>
          <div style={{ fontSize: 13, fontWeight: 600 }}>Session waiting for input</div>
          <div style={{ fontSize: 12, opacity: .7 }}>deploy.sh</div>
        </div>
      </div>
      <p style={{ margin: 0, fontSize: 11, opacity: .5 }}>
        Tap → deep-links into Terminal, scrolled to the point that triggered the alert.
      </p>
    </div>
  );
}
