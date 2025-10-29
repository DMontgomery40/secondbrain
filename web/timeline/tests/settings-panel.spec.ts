import { test, expect } from '@playwright/test';

test.describe('Settings Panel', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the app
    await page.goto('/');
    
    // Wait for the app to load
    await page.waitForLoadState('networkidle', { timeout: 30000 });
    await page.waitForSelector('main, .timeline-main', { timeout: 15000 });
    await page.waitForTimeout(1000);
  });

  test('should open settings panel when clicking settings button', async ({ page }) => {
    // Find and click the settings button (gear icon)
    const settingsButton = page.locator('button.settings-button, button:has-text("⚙️")').first();
    await expect(settingsButton).toBeVisible();
    await settingsButton.click();

    // Wait for settings panel to appear
    await expect(page.locator('.settings-panel')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('h2:has-text("SecondBrain Settings")')).toBeVisible();
  });

  test('should load settings successfully without errors', async ({ page }) => {
    // Open settings panel
    const settingsButton = page.locator('button.settings-button, button:has-text("⚙️")').first();
    await settingsButton.click();

    // Wait for settings panel
    await page.waitForSelector('.settings-panel', { timeout: 5000 });

    // Should NOT see error message
    const errorBox = page.locator('text=/Error loading settings/i');
    await expect(errorBox).not.toBeVisible({ timeout: 3000 });

    // Should see settings tabs
    await expect(page.locator('.settings-tabs')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('button.tab:has-text("Capture")')).toBeVisible();
    await expect(page.locator('button.tab:has-text("OCR")')).toBeVisible();
    await expect(page.locator('button.tab:has-text("Storage")')).toBeVisible();
    await expect(page.locator('button.tab:has-text("Embeddings")')).toBeVisible();
  });

  test('should display settings content when loaded', async ({ page }) => {
    // Open settings panel
    const settingsButton = page.locator('button.settings-button, button:has-text("⚙️")').first();
    await settingsButton.click();

    // Wait for settings to load
    await page.waitForSelector('.settings-panel', { timeout: 5000 });
    await page.waitForSelector('.settings-content', { timeout: 5000 });

    // Should see settings content (not loading spinner)
    const loadingSpinner = page.locator('text=/Loading settings/i');
    await expect(loadingSpinner).not.toBeVisible({ timeout: 3000 });

    // Should see settings sections
    await expect(page.locator('h3:has-text("Capture Settings")')).toBeVisible({ timeout: 3000 });
  });

  test('should be able to switch between tabs', async ({ page }) => {
    // Open settings panel
    const settingsButton = page.locator('button.settings-button, button:has-text("⚙️")').first();
    await settingsButton.click();

    await page.waitForSelector('.settings-panel', { timeout: 5000 });
    await page.waitForSelector('.settings-content', { timeout: 5000 });

    // Click OCR tab
    await page.locator('button.tab:has-text("OCR")').click();
    await page.waitForTimeout(500);
    await expect(page.locator('h3:has-text("OCR Settings")')).toBeVisible();

    // Click Storage tab
    await page.locator('button.tab:has-text("Storage")').click();
    await page.waitForTimeout(500);
    await expect(page.locator('h3:has-text("Storage Settings")')).toBeVisible();

    // Click Embeddings tab
    await page.locator('button.tab:has-text("Embeddings")').click();
    await page.waitForTimeout(500);
    await expect(page.locator('h3:has-text("Embeddings Settings")')).toBeVisible();
  });

  test('should close settings panel when clicking close button', async ({ page }) => {
    // Open settings panel
    const settingsButton = page.locator('button.settings-button, button:has-text("⚙️")').first();
    await settingsButton.click();

    await page.waitForSelector('.settings-panel', { timeout: 5000 });

    // Click close button
    const closeButton = page.locator('button.close-btn, button:has-text("✕")');
    await closeButton.click();

    // Settings panel should disappear
    await expect(page.locator('.settings-panel')).not.toBeVisible({ timeout: 2000 });
  });

  test('should close settings panel when clicking outside', async ({ page }) => {
    // Open settings panel
    const settingsButton = page.locator('button.settings-button, button:has-text("⚙️")').first();
    await settingsButton.click();

    await page.waitForSelector('.settings-panel', { timeout: 5000 });

    // Click on overlay (outside the panel)
    await page.locator('.settings-overlay').click({ position: { x: 10, y: 10 } });

    // Settings panel should disappear
    await expect(page.locator('.settings-panel')).not.toBeVisible({ timeout: 2000 });
  });
});


