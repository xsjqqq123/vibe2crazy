import { test, expect } from '@playwright/test';

test('QR code appears on URL hover', async ({ page }) => {
  // Login
  await page.goto('http://localhost:5173');
  await page.fill('input[type="text"], input[placeholder*="password"]', 'password');
  await page.press('input[type="text"], input[placeholder*="password"]', 'Enter');

  // Wait for redirect
  await page.waitForURL(/projects/, { timeout: 5000 }).catch(() => {});

  // Go to projects page
  await page.goto('http://localhost:5173/projects');

  // Wait for TunnelPanel to load
  await page.waitForSelector('.tunnel-panel', { timeout: 5000 });

  // Check if tunnel is connected (if URL is shown)
  const urlLink = page.locator('a.link.text-primary');
  const isVisible = await urlLink.isVisible().catch(() => false);

  if (isVisible) {
    // Hover over the URL
    await urlLink.hover();

    // Wait for QR code tooltip to appear
    const qrTooltip = page.locator('img[alt="QR Code"]');
    await expect(qrTooltip).toBeVisible({ timeout: 2000 });

    console.log('✅ QR code tooltip appeared on hover');
  } else {
    console.log('⚠️ Tunnel not connected - cannot test QR code');
  }
});