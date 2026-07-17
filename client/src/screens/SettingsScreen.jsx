// termhop client — Screen 8: Settings
import React from 'react';
import { BackIcon } from '../icons';

export default function SettingsScreen({ onBack, onOpenRegenerate }) {
  return (
    <div className="screen">
      <div className="screen-header">
        <button className="btn btn-icon" onClick={onBack} aria-label="Back"><BackIcon /></button>
        <h3>Settings</h3>
      </div>

      <div className="screen-body" style={{ gap: 18 }}>
        <section>
          <h6>Notifications</h6>
          <div className="field"><label>Idle alert threshold</label><input className="input" placeholder="30 seconds" /></div>
          <label className="radio" style={{ justifyContent: 'space-between', display: 'flex', marginTop: 6 }}>
            <span>Sound</span><input type="checkbox" defaultChecked />
          </label>
          <label className="radio" style={{ justifyContent: 'space-between', display: 'flex' }}>
            <span>Vibration</span><input type="checkbox" defaultChecked />
          </label>
        </section>

        <section>
          <h6>Appearance</h6>
          <div className="seg">
            <label className="seg-opt"><input type="radio" name="theme" defaultChecked />Dark</label>
            <label className="seg-opt"><input type="radio" name="theme" />Light</label>
            <label className="seg-opt"><input type="radio" name="theme" />System</label>
          </div>
        </section>

        <section>
          <h6>Default shell</h6>
          <div className="field"><input className="input" defaultValue="Claude Code" /></div>
        </section>

        <section>
          <h6>Security</h6>
          <div className="card" style={{ gap: 6 }}>
            <div className="card-kicker">Device key fingerprint</div>
            <code style={{ fontSize: 12 }}>3F2A · 91C0 · 7B4D · E611</code>
            <button className="btn btn-secondary" style={{ alignSelf: 'flex-start', fontSize: 12 }} onClick={onOpenRegenerate}>
              Regenerate
            </button>
          </div>
        </section>

        <section>
          <h6>About</h6>
          <p style={{ margin: 0, fontSize: 12, opacity: .7 }}>
            termhop v0.4.1 · <a href="/SECURITY.md">SECURITY.md</a> · <a href="/LICENSE">License</a>
          </p>
        </section>
      </div>
    </div>
  );
}
