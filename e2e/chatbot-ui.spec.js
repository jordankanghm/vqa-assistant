// Run in e2e directory using: npx playwright test chatbot-ui.spec.js

const { test, expect } = require('@playwright/test');

const GATEWAY_URL = process.env.GATEWAY_URL || 'http://localhost:8000';
const USER_SERVICE_URL = process.env.USER_SERVICE_URL || 'http://localhost:8003';
const FRONTEND_URL = process.env.FRONTEND_URL || 'http://localhost:3000';

const TEST_USER = {
  username: "testuser",
  email: "test@example.com", 
  password: "password123"
};

// Pre-register test user before each test
test.beforeEach(async ({ request }) => {
  const response = await request.post(`${USER_SERVICE_URL}/register`, {
    headers: { "Content-Type": "application/json" },
    data: TEST_USER
  });

  expect(response.status()).toBeGreaterThanOrEqual(200);  // 200 or 400 OK
  expect(response.status()).toBeLessThan(500);  // reject server error
});

// Delete test user after each test
test.afterEach(async ({ page }) => {
  const response = await page.request.delete(`${USER_SERVICE_URL}/users/${TEST_USER.username}`);
});

const imageUrl = "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg";
// Create a 1x1 transparent PNG buffer (base64 decoded)
const imgBuffer = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8Xw8AAoMBgQLOSTgAAAAASUVORK5CYII=',
  'base64'
);

// === AUTHENTICATION TESTS ===
test.describe('User Authentication', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(FRONTEND_URL);
  });

  test('successful login shows user info and logout button', async ({ page }) => {
    const res = await page.request.post(`${GATEWAY_URL}/auth/login`, {
      data: {
        username: TEST_USER.username,
        password: TEST_USER.password
      }
    });

    if (res.status() !== 200) {
      throw new Error(`Test user ${TEST_USER.username} does not exist or wrong password. Create the user first.`);
    }
    // Login
    await page.getByTestId("header-login").click();
    await page.getByPlaceholder("Username").fill(TEST_USER.username);
    await page.getByPlaceholder("Password").fill(TEST_USER.password);
    await page.getByTestId("modal-submit").click();

    // Verify authenticated state
    await page.waitForTimeout(5000);
    // Take a screenshot for debugging
    await page.screenshot({ path: '/app/debug_login.png', fullPage: true });
    await expect(page.getByText(new RegExp(`Logged in as ${TEST_USER.username}`, 'i'))).toBeVisible();
    await expect(page.getByRole("button", { name: "Logout" })).toBeVisible();
    
    // Login/Signup buttons should be gone
    await expect(page.getByTestId("header-login")).not.toBeVisible();
    await expect(page.getByTestId("header-signup")).not.toBeVisible();
  });

  test('login error displays error message', async ({ page }) => {
    // Mock backend error (intercept API)
    await page.route("**/auth/login", route => 
      route.fulfill({ status: 401, body: JSON.stringify({ detail: "Invalid credentials" }) })
    );

    await page.getByTestId("header-login").click();
    await page.getByPlaceholder("Username").fill("wronguser");
    await page.getByPlaceholder("Password").fill("wrongpass");
    await page.getByTestId("modal-submit").click();

    // Error appears, modal stays open
    await expect(page.locator('[style*="color: red"]').filter({ hasText: /invalid credentials/i })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Log in" })).toBeVisible();
  });

  test('successful registration closes modal and logs in user', async ({ page }) => {
    // Ensure user does not exist before registering
    const response = await page.request.delete(`${USER_SERVICE_URL}/users/newuser`);
    expect(response.status()).toBeGreaterThanOrEqual(200);  // 200 or 404 OK
    expect(response.status()).toBeLessThan(500);  // reject server error

    await page.getByTestId("header-signup").click();
    await page.getByPlaceholder("Username").fill("newuser");
    await page.getByPlaceholder("Email").fill("newuser@example.com");
    await page.getByPlaceholder("Password").fill("password123");
    await page.getByTestId("modal-submit").click();

    // Modal closes, user logged in
    await expect(page.getByRole("heading", { name: "Sign up" })).not.toBeVisible();
    await expect(page.getByText(/logged in as newuser/i)).toBeVisible();
  });

  test('registration error displays error message', async ({ page }) => {
    await page.getByTestId("header-signup").click();
    await page.getByPlaceholder("Username").fill(TEST_USER.username);  // already exists
    await page.getByPlaceholder("Email").fill(TEST_USER.email);
    await page.getByPlaceholder("Password").fill(TEST_USER.password);
    await page.getByTestId("modal-submit").click();

    await page.waitForTimeout(2000);

    await expect(page.locator('[style*="color: red"]').filter({ hasText: /username already registered/i })).toBeVisible();
  });

  test('logout returns to unauthenticated state', async ({ page }) => {
    await page.getByTestId("header-login").click();
    await page.getByPlaceholder("Username").fill(TEST_USER.username);
    await page.getByPlaceholder("Password").fill(TEST_USER.password);
    await page.getByTestId("modal-submit").click();

    await expect(page.getByText(/logged in as testuser/i)).toBeVisible();

    // Logout
    await page.getByRole("button", { name: "Logout" }).click();

    // Back to login state
    await expect(page.getByTestId("header-login")).toBeVisible();
    await expect(page.getByText(/logged in as testuser/i)).not.toBeVisible();
  });
});

// === UNAUTHENTICATED TESTS ===
test.describe('Unauthenticated Chat Management', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(FRONTEND_URL);
  });

  test('Send text message and receive bot reply', async ({ page }) => {
    const textarea = page.locator('textarea[aria-label="Chat input text"]');
    await textarea.fill('What is the capital of France?');
    await textarea.press('Enter');

    const botMessages = page.locator('div.bot-message');
    const lastBotMessage = botMessages.last();
    const botReply = await lastBotMessage.locator('.message-text').textContent();

    expect(botReply.toLowerCase()).toContain("paris");
  });


  test('Upload an image url and get bot reply', async ({ page }) => {
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

    // Assert bot reply
    expect(botReply && botReply.trim().length).toBeGreaterThan(0);
  });

  test('Send text and image, receive combined bot reply', async ({ page }) => {
    const textarea = page.locator('textarea[aria-label="Chat input text"]');
    const message = `${imageUrl} What are the main colours present in this image?`;
    await textarea.fill(message);
    await textarea.press('Enter');

    const botMessages = page.locator('div.bot-message');
    const lastBotMessage = botMessages.last();
    const botReply = await lastBotMessage.locator('.message-text').textContent();

    expect(botReply.toLowerCase()).toContain("green");
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

// === AUTHENTICATED TESTS ===
test.describe('Authenticated Chat Management', () => {
  // Login before each test
  test.beforeEach(async ({ page }) => {
    await page.goto(FRONTEND_URL);
    await page.getByTestId("header-login").click();
    await page.getByPlaceholder("Username").fill(TEST_USER.username);
    await page.getByPlaceholder("Password").fill(TEST_USER.password);
    await page.getByTestId("modal-submit").click();

    // Wait for chats to load
    await page.waitForTimeout(3000);
  });

  test('create new chat adds to dropdown and clears messages', async ({ page }) => {
    const chatSelect = page.locator('select');
    const initialChatCount = await chatSelect.locator('option').count();
    expect(initialChatCount).toBeGreaterThan(1);

    // Create new chat
    await page.locator('button:has-text("New Chat")').click();
    await page.waitForTimeout(2000);

    // New chat appears in dropdown
    const newChatCount = await chatSelect.locator('option').count();
    expect(newChatCount).toBe(initialChatCount + 1);

    // Messages cleared for new chat
    const messageElements = page.locator('[class*="user-message"], [class*="bot-message"]');
    await expect(messageElements).toHaveCount(0);
  });

  test('selecting chat loads its messages', async ({ page }) => {
    // Send message in first chat to have history
    const textarea = page.locator('textarea[aria-label="Chat input text"]');
    await textarea.fill('Test message for chat history');
    await page.locator('button[aria-label="Send message"]').click();
    await page.waitForTimeout(5000);

    // Verify message sent (user message visible)
    await expect(page.locator('.user-message')).toBeVisible();

    // Create new chat (empty)
    await page.locator('button:has-text("New Chat")').click();
    await page.waitForTimeout(2000);
    await expect(page.locator('.user-message, .bot-message')).toHaveCount(0);

    // Switch back to first chat - history should reload
    const chatSelect = page.locator('select');
    const firstChatOption = page.locator('select option:nth-child(2)'); // Skip "Select..."
    const firstChatId = await firstChatOption.getAttribute('value');
    await chatSelect.selectOption(firstChatId);
    await page.waitForTimeout(3000)

    // Original message reappears
    await expect(page.locator('.user-message .message-text')).toContainText('Test message');
  });

  test('new chat uses correct chat_id for auth-inference', async ({ page, request }) => {
    // Monitor network requests
    const authInferenceCalls = [];
    page.on('request', req => {
      if (req.url().includes('/auth-inference') && req.method() === 'POST') {
        authInferenceCalls.push(req.postDataJSON());
      }
    });

    // Create new chat
    await page.locator('button:has-text("New Chat")').click();
    await page.waitForTimeout(2000);

    // Send message in new chat
    await page.locator('textarea[aria-label="Chat input text"]').fill('Test auth inference');
    await page.locator('button[aria-label="Send message"]').click();
    await page.waitForTimeout(5000);

    // Verify auth-inference called with correct chat_id (newly created one)
    expect(authInferenceCalls.length).toBeGreaterThan(0);
    const lastCall = authInferenceCalls[authInferenceCalls.length - 1];
    expect(lastCall).toHaveProperty('chat_id');
    expect(typeof lastCall.chat_id).toBe('number');
    expect(lastCall.user_id).toBeDefined();
  });
});
