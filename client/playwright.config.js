import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 30000,
  fullyParallel: false,
  webServer: {
    command: 'npm run dev -- --port 5273',
    port: 5273,
    reuseExistingServer: false,
    timeout: 30000,
  },
  use: {
    baseURL: 'http://localhost:5273',
    ...devices['Pixel 7'], // mobile viewport — "test in mobile browser" is the literal deliverable
  },
});
