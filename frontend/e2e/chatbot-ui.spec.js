const { test, expect } = require('@playwright/test');

const imageUrl = "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg";

// === Valid input tests ===
test.describe('Valid input tests', () => {
  test('Send text message and receive bot reply', async ({ page }) => {
    await page.goto('http://localhost:3000');
    const textarea = page.locator('textarea[aria-label="Chat input text"]');
    await textarea.fill('What is your name?');
    await textarea.press('Enter');

    const botMessages = page.locator('div.bot-message');
    const lastBotMessage = botMessages.last();
    const botReply = await lastBotMessage.locator('.message-text').textContent();

    expect(botReply.toLowerCase()).toContain("grok");
  });


  test('Upload an image and get bot reply', async ({ page }) => {
    await page.goto('http://localhost:3000');
    
    // Use for model which accepts base64 images
    // // Create a 1x1 transparent PNG buffer (base64 decoded)
    // const imgBuffer = Buffer.from(
    //   'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8Xw8AAoMBgQLOSTgAAAAASUVORK5CYII=',
    //   'base64'
    // );

    // // Upload mock image
    // const fileInput = page.locator('input[type="file"][aria-label="Upload image"]');
    // await fileInput.setInputFiles({
    //   name: 'mock.png',
    //   mimeType: 'image/png',
    //   buffer: imgBuffer,
    // });

    // const sendButton = page.locator('button[aria-label="Send message"]');
    // await sendButton.click();

    const textarea = page.locator('textarea[aria-label="Chat input text"]');
    const message = `[Image Link: ${imageUrl}]`;
    await textarea.fill(message);
    await textarea.press('Enter');

    const botMessages = page.locator('div.bot-message');
    const lastBotMessage = botMessages.last();
    const botReply = await lastBotMessage.locator('.message-text').textContent();

    // Assert bot reply is non-empty
    expect(botReply && botReply.trim().length).toBeGreaterThan(0);
  });


  test('Send text and image, receive combined bot reply', async ({ page }) => {
    await page.goto('http://localhost:3000');
    // Use for model which accepts base64 images
    // const textarea = page.locator('textarea[aria-label="Chat input text"]');
    // await textarea.fill('Hello with image');
    
    // // Create a 1x1 transparent PNG buffer (base64 decoded)
    // const imgBuffer = Buffer.from(
    //   'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8Xw8AAoMBgQLOSTgAAAAASUVORK5CYII=',
    //   'base64'
    // );

    // // Upload mock image
    // const fileInput = page.locator('input[type="file"][aria-label="Upload image"]');
    // await fileInput.setInputFiles({
    //   name: 'mock.png',
    //   mimeType: 'image/png',
    //   buffer: imgBuffer,
    // });

    // const sendButton = page.locator('button[aria-label="Send message"]');
    // await sendButton.click();

    const textarea = page.locator('textarea[aria-label="Chat input text"]');
    const message = `[Image Link: ${imageUrl}] What are the main colours present in this image?`;
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

  test('Send invalid image link does not send image but sends text message', async ({ page }) => {
    await page.goto('http://localhost:3000');
    const textarea = page.locator('textarea[aria-label="Chat input text"]');

    const invalidImageMessage = '[Image Link: ftp://invalid-url.com/image.jpg] Describe this image';
    await textarea.fill(invalidImageMessage);
    await textarea.press('Enter');

    // Bot reply should appear since valid text remains
    const botMessages = page.locator('div.bot-message');
    const lastBotMessage = botMessages.last();
    const textContent = await lastBotMessage.locator('.message-text').textContent();
    await expect(lastBotMessage).toBeVisible({ timeout: 60000 });

    expect(textContent && textContent.trim().length).toBeGreaterThan(0);

    const images = page.locator('img[alt="User upload"]');
    await expect(images).toHaveCount(0);

    expect(textContent).not.toContain('ftp://invalid-url.com');
  });
});