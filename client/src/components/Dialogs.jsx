// termhop client — shared dialogs, rendered at the App root so any screen can trigger them.
import React from 'react';

function stop(e) { e.stopPropagation(); }

export function EncryptionDialog({ open, onClose, cipherSuite, sessionKeyFingerprint }) {
  if (!open) return null;
  return (
    <div className="dialog-backdrop" onClick={onClose}>
      <div className="dialog" onClick={stop}>
        <div className="dialog-title">Encrypted session</div>
        <div className="dialog-body">
          Cipher: {cipherSuite}<br />
          Session key fingerprint: <code>{sessionKeyFingerprint}</code><br />
          The relay cannot read this — it only forwards encrypted bytes between this device and the agent.
        </div>
        <div className="dialog-actions">
          <button className="btn btn-primary" onClick={onClose}>Done</button>
        </div>
      </div>
    </div>
  );
}

export function RegenerateKeyDialog({ open, onCancel, onConfirm }) {
  if (!open) return null;
  return (
    <div className="dialog-backdrop" onClick={onCancel}>
      <div className="dialog" onClick={stop}>
        <div className="dialog-title">Regenerate device key?</div>
        <div className="dialog-body">
          Every paired agent will need to be re-verified against the new fingerprint. This can't be undone.
        </div>
        <div className="dialog-actions">
          <button className="btn btn-secondary" onClick={onCancel}>Cancel</button>
          <button className="btn btn-primary" onClick={onConfirm}>Regenerate</button>
        </div>
      </div>
    </div>
  );
}

export function UnpairDialog({ agentName, onCancel, onConfirm }) {
  if (!agentName) return null;
  return (
    <div className="dialog-backdrop" onClick={onCancel}>
      <div className="dialog" onClick={stop}>
        <div className="dialog-title">Unpair {agentName}?</div>
        <div className="dialog-body">
          This device will lose access to run commands on this agent. You'll need to pair again to reconnect.
        </div>
        <div className="dialog-actions">
          <button className="btn btn-secondary" onClick={onCancel}>Cancel</button>
          <button className="btn btn-primary" onClick={onConfirm}>Unpair</button>
        </div>
      </div>
    </div>
  );
}
