// Hosted accounts are an optional adapter. A plain open-source build leaves
// this unset and retains direct pairing with any self-hosted relay.
const CONTROL_PLANE_URL = (import.meta.env.VITE_CONTROL_PLANE_URL || '').replace(/\/$/, '');
const STORAGE_KEY = 'termhop.account.v1';
export const hostedAccountsEnabled = Boolean(CONTROL_PLANE_URL);

export class AccountError extends Error {}

export function controlPlaneUrl(path = '') {
  if (!hostedAccountsEnabled) return '';
  return `${CONTROL_PLANE_URL}${path}`;
}

export function loadAccount() {
  try {
    const value = JSON.parse(localStorage.getItem(STORAGE_KEY));
    return value?.accessToken && value?.email ? value : null;
  } catch {
    return null;
  }
}

export function clearAccount() {
  localStorage.removeItem(STORAGE_KEY);
}

export function takeHandoffFromLocation() {
  const params = new URLSearchParams(window.location.hash.replace(/^#/, ''));
  const handoff = params.get('handoff');
  if (!handoff) return null;
  params.delete('handoff');
  const cleanHash = params.toString() ? `#${params}` : '';
  window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}${cleanHash}`);
  return handoff;
}

export async function exchangeHandoff(handoff) {
  const response = await fetch(controlPlaneUrl('/api/client/exchange'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ handoff }),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new AccountError(body.error || 'Could not complete login');
  const account = {
    accessToken: body.access_token,
    email: body.email,
    relayUrl: body.relay_url,
    relayStatus: body.relay_status,
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(account));
  return account;
}

export async function refreshAccount(account) {
  const response = await fetch(controlPlaneUrl('/api/client/me'), {
    headers: { Authorization: `Bearer ${account.accessToken}` },
  });
  if (!response.ok) {
    clearAccount();
    throw new AccountError('Your account session expired; log in again');
  }
  const body = await response.json();
  const refreshed = {
    ...account,
    email: body.email,
    relayUrl: body.relay_url,
    relayStatus: body.relay_status,
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(refreshed));
  return refreshed;
}

export async function logoutAccount(account) {
  try {
    await fetch(controlPlaneUrl('/api/client/logout'), {
      method: 'POST',
      headers: { Authorization: `Bearer ${account.accessToken}` },
    });
  } finally {
    clearAccount();
  }
}
