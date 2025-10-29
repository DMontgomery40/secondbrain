import { test, expect } from '@playwright/test';

test.describe('Multi-Day Search Feature', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the app
    await page.goto('/');

    // Wait for the app to load - give it extra time for vite to compile
    await page.waitForLoadState('networkidle', { timeout: 30000 });

    // Wait for React to render - look for any main content
    await page.waitForSelector('main, .timeline-main', { timeout: 15000 });

    // Wait a bit more for full hydration
    await page.waitForTimeout(1000);
  });

  test('should display date range preset buttons', async ({ page }) => {
    // Check all preset buttons are visible
    await expect(page.locator('button:has-text("Last 7 Days")')).toBeVisible();
    await expect(page.locator('button:has-text("Last 30 Days")')).toBeVisible();
    await expect(page.locator('button:has-text("All Time")')).toBeVisible();
    await expect(page.locator('button:has-text("Custom")')).toBeVisible();

    // Check that "Last 7 Days" is selected by default (has blue background)
    const lastSevenDaysBtn = page.locator('button:has-text("Last 7 Days")');
    const bgColor = await lastSevenDaysBtn.evaluate((el) => window.getComputedStyle(el).backgroundColor);
    expect(bgColor).toContain('rgb(74, 144, 226)'); // #4a90e2
  });

  test('should switch between date range presets', async ({ page }) => {
    // Click "Last 30 Days"
    await page.locator('button:has-text("Last 30 Days")').click();
    await page.waitForTimeout(500);

    // Verify it's now active
    const last30DaysBtn = page.locator('button:has-text("Last 30 Days")');
    const bgColor30 = await last30DaysBtn.evaluate((el) => window.getComputedStyle(el).backgroundColor);
    expect(bgColor30).toContain('rgb(74, 144, 226)');

    // Click "All Time"
    await page.locator('button:has-text("All Time")').click();
    await page.waitForTimeout(500);

    // Verify it's now active
    const allTimeBtn = page.locator('button:has-text("All Time")');
    const bgColorAll = await allTimeBtn.evaluate((el) => window.getComputedStyle(el).backgroundColor);
    expect(bgColorAll).toContain('rgb(74, 144, 226)');
  });

  test('should show custom date inputs when Custom is selected', async ({ page }) => {
    // Initially, custom date inputs should not be visible
    await expect(page.locator('input[type="date"]').first()).not.toBeVisible();

    // Click "Custom"
    await page.locator('button:has-text("Custom")').click();
    await page.waitForTimeout(500);

    // Now custom date inputs should be visible
    const dateInputs = page.locator('input[type="date"]');
    await expect(dateInputs.first()).toBeVisible();
    await expect(dateInputs.nth(1)).toBeVisible();

    // Check for "From:" and "To:" labels
    await expect(page.locator('label:has-text("From:")')).toBeVisible();
    await expect(page.locator('label:has-text("To:")')).toBeVisible();
  });

  test('should allow selecting custom date range (10/28 and 10/29)', async ({ page }) => {
    // Click "Custom" button
    await page.locator('button:has-text("Custom")').click();
    await page.waitForTimeout(500);

    // Get the date input fields
    const dateInputs = page.locator('input[type="date"]');
    const startDateInput = dateInputs.first();
    const endDateInput = dateInputs.nth(1);

    // Set start date to 2025-10-28
    await startDateInput.fill('2025-10-28');
    await page.waitForTimeout(300);

    // Set end date to 2025-10-29
    await endDateInput.fill('2025-10-29');
    await page.waitForTimeout(300);

    // Verify the values are set
    await expect(startDateInput).toHaveValue('2025-10-28');
    await expect(endDateInput).toHaveValue('2025-10-29');
  });

  test('should submit query and receive AI answer with custom date range', async ({ page }) => {
    // Set custom date range (10/28 and 10/29)
    await page.locator('button:has-text("Custom")').click();
    await page.waitForTimeout(500);

    const dateInputs = page.locator('input[type="date"]');
    await dateInputs.first().fill('2025-10-28');
    await dateInputs.nth(1).fill('2025-10-29');
    await page.waitForTimeout(300);

    // Enter a query
    const textarea = page.locator('textarea[placeholder*="What was I working on"]');
    await textarea.fill('What did I work on?');

    // Click the Ask button
    const askButton = page.locator('button.ask-button, button:has-text("Ask")');
    await askButton.click();

    // Button should show "Thinking…" while processing
    await expect(askButton).toContainText('Thinking…', { timeout: 2000 });

    // Wait for the AI answer section to appear (max 30 seconds for API call)
    const aiAnswerSection = page.locator('.ai-answer');
    await expect(aiAnswerSection).toBeVisible({ timeout: 30000 });

    // Verify the answer header is present
    await expect(page.locator('h3:has-text("🤖 AI Answer")')).toBeVisible();

    // Verify there is actual text content in the answer (not just error)
    const answerText = await aiAnswerSection.innerText();
    expect(answerText.length).toBeGreaterThan(50); // Should have substantial content
    expect(answerText).not.toContain('Error:');

    // Button should return to "Ask" after completion
    await expect(askButton).toContainText('Ask', { timeout: 5000 });
  });

  test('should submit query with Last 7 Days preset and receive AI answer', async ({ page }) => {
    // "Last 7 Days" is selected by default, so just enter query
    const textarea = page.locator('textarea[placeholder*="What was I working on"]');
    await textarea.fill('Summarize my recent activity');

    // Click the Ask button
    const askButton = page.locator('button.ask-button, button:has-text("Ask")');
    await askButton.click();

    // Wait for thinking state
    await expect(askButton).toContainText('Thinking…', { timeout: 2000 });

    // Wait for the AI answer
    const aiAnswerSection = page.locator('.ai-answer');
    await expect(aiAnswerSection).toBeVisible({ timeout: 30000 });

    // Verify answer content
    const answerText = await aiAnswerSection.innerText();
    expect(answerText.length).toBeGreaterThan(20);
    expect(answerText).not.toContain('Error:');
  });

  test('should verify semantic and reranker checkboxes work', async ({ page }) => {
    // Find semantic checkbox
    const semanticCheckbox = page.locator('input[type="checkbox"]').first();
    await expect(semanticCheckbox).toBeChecked(); // Should be checked by default

    // Find reranker checkbox
    const rerankerCheckbox = page.locator('input[type="checkbox"]').nth(1);
    await expect(rerankerCheckbox).not.toBeChecked(); // Should be unchecked by default

    // Toggle semantic off
    await semanticCheckbox.click();
    await expect(semanticCheckbox).not.toBeChecked();

    // Reranker should be disabled when semantic is off
    await expect(rerankerCheckbox).toBeDisabled();

    // Toggle semantic back on
    await semanticCheckbox.click();
    await expect(semanticCheckbox).toBeChecked();

    // Reranker should be enabled again
    await expect(rerankerCheckbox).not.toBeDisabled();
  });

  test('should verify Max Results input works', async ({ page }) => {
    // Find the Max Results input
    const maxResultsInput = page.locator('input[type="number"]').first();

    // Should have default value of 20
    await expect(maxResultsInput).toHaveValue('20');

    // Change value
    await maxResultsInput.fill('15');
    await expect(maxResultsInput).toHaveValue('15');

    // Verify min/max attributes
    const min = await maxResultsInput.getAttribute('min');
    const max = await maxResultsInput.getAttribute('max');
    expect(min).toBe('5');
    expect(max).toBe('50');
  });

  test('should handle empty query gracefully', async ({ page }) => {
    // Don't enter any query
    const askButton = page.locator('button.ask-button, button:has-text("Ask")');

    // Button should be disabled when query is empty
    await expect(askButton).toBeDisabled();

    // Enter a query
    const textarea = page.locator('textarea[placeholder*="What was I working on"]');
    await textarea.fill('test query');

    // Button should now be enabled
    await expect(askButton).not.toBeDisabled();
  });
});
