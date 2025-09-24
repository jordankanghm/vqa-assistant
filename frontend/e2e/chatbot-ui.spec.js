const { test, expect } = require('@playwright/test');

test('Send text message and receive bot reply', async ({ page }) => {
  await page.goto('http://localhost:3000');
  const textarea = page.locator('textarea[aria-label="Chat input text"]');
  await textarea.fill('Hello backend');
  await textarea.press('Enter');

  await expect(page.locator('div[role="button"] >> text=LangChain result for: Hello backend')).toBeVisible({ timeout: 60000 });
});


test('Upload an image and get bot reply', async ({ page }) => {
  await page.goto('http://localhost:3000');
  
  // Create a 1x1 transparent PNG buffer (base64 decoded)
  const imgBuffer = Buffer.from(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8Xw8AAoMBgQLOSTgAAAAASUVORK5CYII=',
    'base64'
  );

  // Upload mock image
  const fileInput = page.locator('input[type="file"][aria-label="Upload image"]');
  await fileInput.setInputFiles({
    name: 'mock.png',
    mimeType: 'image/png',
    buffer: imgBuffer,
  });

  const sendButton = page.locator('button[aria-label="Send message"]');
  await sendButton.click();

  const botImages = page.locator('div[role="button"] img');
  const count = await botImages.count();
  expect(count).toBeGreaterThan(0);
});


test('Send text and image, receive combined bot reply', async ({ page }) => {
  await page.goto('http://localhost:3000');
  const textarea = page.locator('textarea[aria-label="Chat input text"]');
  await textarea.fill('Hello with image');
  
  // Create a 1x1 transparent PNG buffer (base64 decoded)
  const imgBuffer = Buffer.from(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8Xw8AAoMBgQLOSTgAAAAASUVORK5CYII=',
    'base64'
  );

  // Upload mock image
  const fileInput = page.locator('input[type="file"][aria-label="Upload image"]');
  await fileInput.setInputFiles({
    name: 'mock.png',
    mimeType: 'image/png',
    buffer: imgBuffer,
  });

  const sendButton = page.locator('button[aria-label="Send message"]');
  await sendButton.click();

  await expect(page.locator('div[role="button"] >> text=LangChain result for: Hello with image')).toBeVisible({ timeout: 60000 });
  
  const botImages = page.locator('div[role="button"] img');
  const count = await botImages.count();
  expect(count).toBeGreaterThan(0);
});
