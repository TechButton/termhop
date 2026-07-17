// termhop client — Screen 3: New Session Launcher
import React, { useState } from 'react';
import { BackIcon, WarningIcon } from '../icons';

const SHELLS = ['Claude Code', 'Codex CLI', 'Aider', 'cmd.exe', 'PowerShell', 'bash', 'Any CLI (custom)'];

export default function NewSessionScreen({ onBack, onLaunch, recentDirs = ['~/projects/termhop-client', '~/api/server'] }) {
  const [shell, setShell] = useState('Claude Code');
  const [customCmd, setCustomCmd] = useState('');
  const [workdir, setWorkdir] = useState('');
  // Ground rule: auto-accept / skip-permissions defaults OFF, always — see CONTRIBUTING.md.
  const [skipPerms, setSkipPerms] = useState(false);
  const [strictInput, setStrictInput] = useState(false);

  return (
    <div className="screen">
      <div className="screen-header">
        <button className="btn btn-icon" onClick={onBack} aria-label="Back"><BackIcon /></button>
        <h3>New session</h3>
      </div>

      <div className="screen-body">
        <div className="field">
          <label>Shell</label>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {SHELLS.map((label) => (
              <label key={label} className="radio">
                <input type="radio" name="shell" checked={shell === label} onChange={() => setShell(label)} />
                {label}
              </label>
            ))}
          </div>
          {shell === 'Any CLI (custom)' && (
            <input
              className="input" style={{ marginTop: 8 }} placeholder="Custom command…"
              value={customCmd} onChange={(e) => setCustomCmd(e.target.value)}
            />
          )}
        </div>

        <div className="field">
          <label>Working directory</label>
          <input className="input" placeholder="~/projects/…" value={workdir} onChange={(e) => setWorkdir(e.target.value)} />
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 6 }}>
            {recentDirs.map((dir) => (
              <span key={dir} className="tag tag-neutral" style={{ cursor: 'pointer' }} onClick={() => setWorkdir(dir)}>{dir}</span>
            ))}
          </div>
        </div>

        <div className="hr" />

        <label className="radio" style={{ justifyContent: 'space-between', display: 'flex' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            Skip permissions
            {skipPerms && <span style={{ color: 'var(--color-accent)' }}><WarningIcon /></span>}
          </span>
          <input type="checkbox" checked={skipPerms} onChange={() => setSkipPerms((v) => !v)} />
        </label>
        <p style={{ margin: 0, fontSize: 11, opacity: .55 }}>
          Off by default. Auto-accept must never be the default — this stays a deliberate opt-in each session.
        </p>

        <label className="radio" style={{ justifyContent: 'space-between', display: 'flex' }}>
          <span>Strict input</span>
          <input type="checkbox" checked={strictInput} onChange={() => setStrictInput((v) => !v)} />
        </label>
      </div>

      <div className="screen-footer">
        <button
          className="btn btn-primary btn-block" style={{ justifyContent: 'center' }}
          onClick={() => onLaunch({ shell, customCmd, workdir, skipPerms, strictInput })}
        >
          Launch
        </button>
      </div>
    </div>
  );
}
