// termhop client — App root. Routes between the 8 screens and hosts the
// shared dialogs (encryption info, key regen, unpair confirm) that any
// screen can trigger.
import React, { useState } from 'react';
import './styles/tokens.css';
import './styles/components.css';

import PairingScreen from './screens/PairingScreen';
import HomeScreen from './screens/HomeScreen';
import NewSessionScreen from './screens/NewSessionScreen';
import TerminalScreen from './screens/TerminalScreen';
import NotificationScreen from './screens/NotificationScreen';
import AgentStatusScreen from './screens/AgentStatusScreen';
import PortForwardingScreen from './screens/PortForwardingScreen';
import SettingsScreen from './screens/SettingsScreen';
import { EncryptionDialog, RegenerateKeyDialog, UnpairDialog } from './components/Dialogs';

export default function App() {
  const [screen, setScreen] = useState('pairing');
  const [activeSession, setActiveSession] = useState(null);

  const [showEncryptionInfo, setShowEncryptionInfo] = useState(false);
  const [showRegenerate, setShowRegenerate] = useState(false);
  const [unpairTarget, setUnpairTarget] = useState(null);

  function openSession(id) {
    setActiveSession({ id, title: 'termhop-client — main' });
    setScreen('terminal');
  }

  return (
    <div className="theme-dark" style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {screen === 'pairing' && (
        <PairingScreen agentHostname="workstation-01" onPaired={() => setScreen('home')} />
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
          onBack={() => setScreen('home')}
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

      <EncryptionDialog
        open={showEncryptionInfo}
        onClose={() => setShowEncryptionInfo(false)}
        cipherSuite="X25519 + ChaCha20-Poly1305"
        sessionKeyFingerprint="91C0 7B4D E611"
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
