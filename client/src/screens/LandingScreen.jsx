import React from 'react';
import { controlPlaneUrl, hostedAccountsEnabled } from '../lib/accountClient';

export default function LandingScreen({ account, loginState, loginError, savedDevices, reconnecting, onReconnect, onPair, onLogout }) {
  return (
    <div className="screen landing-screen">
      <header className="landing-nav">
        <a className="wordmark" href="https://app.42oclock.com/">termhop</a>
        <div className="landing-nav-actions">
          {hostedAccountsEnabled && <a className="btn btn-ghost" href={controlPlaneUrl('/dashboard')}>Account</a>}
          {account ? (
            <button className="btn btn-secondary" onClick={onLogout}>Log out</button>
          ) : hostedAccountsEnabled ? (
            <a className="btn btn-secondary" href={controlPlaneUrl('/client')}>Log in</a>
          ) : null}
        </div>
      </header>

      <main className="landing-main">
        <section className="landing-hero">
          <div className="eyebrow">End-to-end encrypted remote terminal</div>
          <h1>Your terminal,<br />wherever you are.</h1>
          <p>Run Codex, Claude Code, PowerShell, or any CLI on your own computer and control it securely from this browser.</p>
          {loginState === 'exchanging' && <div className="notice">Completing secure login…</div>}
          {loginError && <div className="notice notice-error">Login failed: {loginError}</div>}
          {account ? (
            <div className="landing-cta">
              <button className="btn btn-primary" onClick={onPair}>Pair a computer</button>
              <span className="account-label">Signed in as {account.email}</span>
            </div>
          ) : hostedAccountsEnabled ? (
            <div className="landing-cta">
              <a className="btn btn-primary" href={controlPlaneUrl('/client')}>Log in to continue</a>
              <button className="btn btn-ghost" onClick={onPair}>Use a self-hosted relay</button>
            </div>
          ) : (
            <div className="landing-cta">
              <button className="btn btn-primary" onClick={onPair}>Pair your relay</button>
              <span className="account-label">Self-hosted mode</span>
            </div>
          )}
        </section>

        <section className="landing-status card">
          <div><span className="status-dot status-dot--live" /> Relay blind by design</div>
          <p>Terminal bytes are encrypted between this browser and your agent. Account login supplies routing and saved-device metadata, never terminal keys.</p>
          {account?.relayUrl && <code>{account.relayUrl}</code>}
          {savedDevices.length > 0 && <div className="saved-device-list">
            <h4>Saved computers</h4>
            {savedDevices.map((device) => (
              <button className="btn btn-secondary btn-block" key={device.deviceId} onClick={() => onReconnect(device)} disabled={reconnecting === device.deviceId}>
                <span className="status-dot status-dot--idle" /> {reconnecting === device.deviceId ? 'Reconnecting…' : device.hostname}
              </button>
            ))}
          </div>}
        </section>
      </main>
    </div>
  );
}
