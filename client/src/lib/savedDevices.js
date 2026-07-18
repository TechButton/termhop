// Durable device credentials never leave this browser. The hosted account
// stores routing/profile information only; clearing site data intentionally
// requires a fresh out-of-band pairing.
const STORAGE_KEY = 'termhop.devices.v1';

export function loadSavedDevices() {
  try {
    const devices = JSON.parse(localStorage.getItem(STORAGE_KEY));
    return Array.isArray(devices) ? devices : [];
  } catch {
    return [];
  }
}

export function saveDevice(device) {
  const devices = loadSavedDevices().filter((entry) => entry.deviceId !== device.deviceId);
  devices.push({ ...device, savedAt: Date.now() });
  localStorage.setItem(STORAGE_KEY, JSON.stringify(devices));
  return devices;
}
