// termhop client E2E — the literal PROJECT_PLAN.md step 3 deliverable:
// "test in mobile browser" against a REAL relay-server + REAL Linux agent
// (not mocks). Boots both via e2e/boot_backend.py, captures the agent's
// real pairing URI, drives the actual app UI (paste-link tab — camera QR
// scanning is out of scope, which is also why paste-link exists), and
// asserts a typed command's echo appears in the real rendered terminal.
import { test, expect } from '@playwright/test';
import { spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const AGENT_PYTHON = path.join(__dirname, '..', '..', 'agent', '.venv', 'bin', 'python');
const BOOT_SCRIPT = path.join(__dirname, 'boot_backend.py');

let backendProc;
let pairingLink;

test.beforeAll(async () => {
  backendProc = spawn(AGENT_PYTHON, [BOOT_SCRIPT], { stdio: ['ignore', 'pipe', 'pipe'] });

  pairingLink = await new Promise((resolve, reject) => {
    let buffer = '';
    const timeout = setTimeout(() => reject(new Error('backend harness did not become ready in time')), 20000);

    backendProc.stdout.on('data', (chunk) => {
      buffer += chunk.toString();
      const match = buffer.match(/PAIRING_LINK=(termhop:\/\/\S+)/);
      if (match) {
        clearTimeout(timeout);
        resolve(match[1]);
      }
    });
    backendProc.stderr.on('data', (chunk) => process.stderr.write(chunk));
    backendProc.on('exit', (code) => {
      clearTimeout(timeout);
      reject(new Error(`backend harness exited early with code ${code}`));
    });
  });
});

test.afterAll(() => {
  backendProc?.kill();
});

test('pairs against a real relay+agent and echoes a real command', async ({ page }) => {
  await page.goto('/');

  await page.getByLabel('Paste link').check();
  await page.getByPlaceholder(/termhop:\/\/pair/).fill(pairingLink);
  await page.getByRole('button', { name: 'Pair device' }).click();

  await expect(page.getByText('Paired ✓')).toBeVisible({ timeout: 10000 });

  // Real xterm.js terminal should now be mounted and streaming.
  const terminal = page.locator('.xterm-screen, .xterm');
  await expect(terminal).toBeVisible({ timeout: 5000 });

  await page.getByPlaceholder('Type a command…').fill('echo PLAYWRIGHT_E2E_CANARY');
  await page.getByPlaceholder('Type a command…').press('Enter');

  await expect(page.locator('.xterm-rows, .xterm')).toContainText('PLAYWRIGHT_E2E_CANARY', { timeout: 10000 });
});
