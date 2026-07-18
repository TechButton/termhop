// termhop client — App root. Routes between the 8 screens and hosts the
// shared dialogs (encryption info, key regen, unpair confirm) that any
// screen can trigger.
import React, { lazy, Suspense, useEffect, useState } from 'react';
import './styles/tokens.css';
import './styles/components.css';

import PairingScreen from './screens/PairingScreen';
import LandingScreen from './screens/LandingScreen';
import HomeScreen from './screens/HomeScreen';
import NewSessionScreen from './screens/NewSessionScreen';
import NotificationScreen from './screens/NotificationScreen';
import AgentStatusScreen from './screens/AgentStatusScreen';
import PortForwardingScreen from './screens/PortForwardingScreen';
import SettingsScreen from './screens/SettingsScreen';
import { EncryptionDialog, RegenerateKeyDialog, UnpairDialog } from './components/Dialogs';
import { clearAccount, exchangeHandoff, loadAccount, logoutAccount, refreshAccount, takeHandoffFromLocation } from './lib/accountClient';
import { loadSavedDevices } from './lib/savedDevices';
import { RelayClient } from './lib/relayClient';

// xterm.js is the largest client dependency. Load it only when a terminal is
// opened so pairing/settings screens stay quick on mobile connections.
const TerminalScreen = lazy(() => import('./screens/TerminalScreen'));

export default function App() {
  const [screen, setScreen] = useState('landing');
  const [account, setAccount] = useState(() => loadAccount());
  const [loginState, setLoginState] = useState('idle');
  const [loginError, setLoginError] = useState('');
  const [savedDevices, setSavedDevices] = useState(() => loadSavedDevices());
  const [reconnecting, setReconnecting] = useState(null);
  const [activeDevice, setActiveDevice] = useState(null);
  const [activeSession, setActiveSession] = useState(null);
  // The live RelayClient from a real pairing — the one WebSocket connection
  // must be threaded through into TerminalScreen unmodified (the relay ties
  // a session to that specific socket; reconnecting means re-pairing from
  // scratch, not resuming). null while on fixture-driven screens.
  const [relayClient, setRelayClient] = useState(null);
  const [sessionFingerprint, setSessionFingerprint] = useState(null);

  const [showEncryptionInfo, setShowEncryptionInfo] = useState(false);
  const [showRegenerate, setShowRegenerate] = useState(false);
  const [unpairTarget, setUnpairTarget] = useState(null);
  const visibleSavedDevices = savedDevices.filter(
    (device) => !device.accountEmail || device.accountEmail === account?.email
  );

  useEffect(() => {
    const handoff = takeHandoffFromLocation();
    if (!handoff) {
      if (account) refreshAccount(account).then(setAccount).catch((error) => {
        setAccount(null);
        setLoginError(error.message);
      });
      return;
    }
    setLoginState('exchanging');
    exchangeHandoff(handoff)
      .then((nextAccount) => { setAccount(nextAccount); setLoginState('authenticated'); })
      .catch((error) => { clearAccount(); setAccount(null); setLoginError(error.message); setLoginState('failed'); });
  }, []); // Account is intentionally read once on boot; refresh updates state without re-running this effect.

  function openSession(id) {
    setActiveSession({ id, title: 'termhop-client — main' });
    setRelayClient(null); // fixture-driven session, not a real paired connection
    setScreen('terminal');
  }

  // The agent streams its one PTY immediately after pair_complete — there's
  // no session list to choose from yet (agent doesn't support multi-session
  // — see agent/linux/README.md), so pairing routes straight to the
  // terminal screen rather than home.
  function handlePaired({ client, sessionId, agentHostname, fingerprint, device = null }) {
    setRelayClient(client);
    setSessionFingerprint(fingerprint);
    setActiveDevice(device);
    setActiveSession({ id: sessionId, title: agentHostname ? `termhop — ${agentHostname}` : 'termhop-client — main' });
    setScreen('terminal');
    setSavedDevices(loadSavedDevices());
  }

  async function reconnectDevice(device, attempts = 1) {
    setReconnecting(device.deviceId);
    setLoginError('');
    for (let attempt = 1; attempt <= attempts; attempt += 1) {
      const client = new RelayClient(device.relayUrl);
      try {
        await client.connect();
        await client.sendResumeRequest(device);
        const details = await client.awaitResumeAndComplete();
        handlePaired({ client, ...details, device });
        setReconnecting(null);
        return;
      } catch (error) {
        client.close();
        if (attempt === attempts) setLoginError(error.message || 'Device is offline');
        else await new Promise((resolve) => setTimeout(resolve, 5000));
      }
    }
    setReconnecting(null);
  }

  // app-shell owns the full dynamic viewport and paints the theme background;
  // each screen then flexes to that complete area at phone or desktop sizes.
  return (
    <div
      className="app-shell theme-dark"
    >
      <Suspense fallback={<div className="screen screen-loading">Loading terminal…</div>}>
        {screen === 'landing' && (
          <LandingScreen
            account={account}
            loginState={loginState}
            loginError={loginError}
            savedDevices={visibleSavedDevices}
            reconnecting={reconnecting}
            onReconnect={reconnectDevice}
            onPair={() => setScreen('pairing')}
            onLogout={async () => { await logoutAccount(account); setAccount(null); }}
          />
        )}
        {screen === 'pairing' && (
          <PairingScreen accountEmail={account?.email} onPaired={handlePaired} />
        )}

      {screen === 'home' && (
        <HomeScreen
          onOpenSession={openSession}
          onNewSession={() => setScreen('newSession')}
          onSettings={() => setScreen('settings')}
          onAgents={() => setScreen('agentStatus')}
          onPorts={() => setScreen('portForwarding')}
          onNotificationDemo={() => setScreen('notification')}
        />
      )}

      {screen === 'newSession' && (
        <NewSessionScreen
          onBack={() => setScreen('home')}
          onLaunch={(config) => { setActiveSession({ id: 'new', title: config.workdir || config.shell }); setScreen('terminal'); }}
        />
      )}

      {screen === 'terminal' && (
        <TerminalScreen
          session={activeSession}
          relayClient={relayClient}
          onBack={() => setScreen(relayClient ? 'landing' : 'home')}
          onDisconnected={() => {
            setScreen('landing');
            setLoginError('Connection interrupted; waiting for the agent to return…');
            if (activeDevice) reconnectDevice(activeDevice, 12);
          }}
          onOpenEncryptionInfo={() => setShowEncryptionInfo(true)}
        />
      )}

      {screen === 'notification' && (
        <NotificationScreen onOpenTerminal={() => openSession('deploy.sh')} />
      )}

      {screen === 'agentStatus' && (
        <AgentStatusScreen
          onBack={() => setScreen('home')}
          onAddAgent={() => setScreen('pairing')}
          onRequestUnpair={setUnpairTarget}
        />
      )}

      {screen === 'portForwarding' && (
        <PortForwardingScreen onBack={() => setScreen('home')} onAddForward={() => {}} />
      )}

        {screen === 'settings' && (
          <SettingsScreen onBack={() => setScreen('home')} onOpenRegenerate={() => setShowRegenerate(true)} />
        )}
      </Suspense>

      <EncryptionDialog
        open={showEncryptionInfo}
        onClose={() => setShowEncryptionInfo(false)}
        cipherSuite="X25519 + HKDF-SHA256 + XChaCha20-Poly1305"
        sessionKeyFingerprint={sessionFingerprint || 'Unavailable for this demo session'}
      />
      <RegenerateKeyDialog
        open={showRegenerate}
        onCancel={() => setShowRegenerate(false)}
        onConfirm={() => setShowRegenerate(false) /* TODO: wire real key rotation */}
      />
      <UnpairDialog
        agentName={unpairTarget}
        onCancel={() => setUnpairTarget(null)}
        onConfirm={() => setUnpairTarget(null) /* TODO: wire real unpair call */}
      />
    </div>
  );
}
