// Run in e2e directory using: npx playwright test chatbot-ui.spec.js

const { test, expect } = require('@playwright/test');

const imageUrl = "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg";
// Create a 1x1 transparent PNG buffer (base64 decoded)
const imgBuffer = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8Xw8AAoMBgQLOSTgAAAAASUVORK5CYII=',
  'base64'
);

// === Valid input tests ===
test.describe('Valid input tests', () => {
  test('Send text message and receive bot reply', async ({ page }) => {
    await page.goto('http://localhost:3000');
    const textarea = page.locator('textarea[aria-label="Chat input text"]');
    await textarea.fill('What is the capital of France?');
    await textarea.press('Enter');

    const botMessages = page.locator('div.bot-message');
    const lastBotMessage = botMessages.last();
    const botReply = await lastBotMessage.locator('.message-text').textContent();

    expect(botReply.toLowerCase()).toContain("paris");
  });


  test('Upload an image url and get bot reply', async ({ page }) => {
    await page.goto('http://localhost:3000');
    
    const textarea = page.locator('textarea[aria-label="Chat input text"]');
    await textarea.fill(imageUrl);
    await textarea.press('Enter');

    const botMessages = page.locator('div.bot-message');
    const lastBotMessage = botMessages.last();
    const botReply = await lastBotMessage.locator('.message-text').textContent();

    // Assert bot reply is non-empty
    expect(botReply && botReply.trim().length).toBeGreaterThan(0);
  });

  test('Upload a base64 image and get bot reply', async ({ page }) => {
    await page.goto('http://localhost:3000');

    // Upload mock image
    const fileInput = page.locator('input[type="file"][aria-label="Upload image"]');
    await fileInput.setInputFiles({
      name: 'mock.png',
      mimeType: 'image/png',
      buffer: imgBuffer,
    });

    const sendButton = page.locator('button[aria-label="Send message"]');
    await sendButton.click();

    const botMessages = page.locator('div.bot-message');
    const lastBotMessage = botMessages.last();
    const botReply = await lastBotMessage.locator('.message-text').textContent();

    // Assert bot reply contains 'blank' or 'transparent'
    expect(botReply && botReply.trim().length).toBeGreaterThan(0);
    expect(botReply.toLowerCase()).toMatch(/blank|transparent/);
  });

  test('Send text and image, receive combined bot reply', async ({ page }) => {
    await page.goto('http://localhost:3000');

    const textarea = page.locator('textarea[aria-label="Chat input text"]');
    const message = `${imageUrl} What are the main colours present in this image?`;
    await textarea.fill(message);
    await textarea.press('Enter');

    const botMessages = page.locator('div.bot-message');
    const lastBotMessage = botMessages.last();
    const botReply = await lastBotMessage.locator('.message-text').textContent();

    expect(botReply.toLowerCase()).toContain("green");
  });
});

// === Invalid input tests ===
test.describe('Invalid input tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:3000');
  });

  test('Send empty message does not send', async ({ page }) => {
    const textarea = page.locator('textarea[aria-label="Chat input text"]');
    await textarea.fill('   ');  // whitespace only
    await textarea.press('Enter');

    // Bot reply should not appear (no new user message sent)
    const botMessages = page.locator('div.bot-message');
    await expect(botMessages).toHaveCount(0);
  });
});