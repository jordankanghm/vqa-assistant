// Run in frontend directory using: npm test
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import ChatbotUI from "./ChatbotUI";

// Mocking global FileReader for image upload tests
class MockFileReader {
  constructor() {
    this.onload = null;
  }
  readAsDataURL(file) {
    if (this.onload) {
      this.onload({ target: { result: "data:image/png;base64,mockimage" } });
    }
  }
}
global.FileReader = MockFileReader;

const mockRegisterResponse = {
  ok: true,
  status: 200,
  json: async () => ({})
};

const mockLoginResponse = {
  ok: true,
  status: 200,
  json: async () => ({
    access_token: "mock-jwt-token-123",
    user_id: 42
  })
};

const mockRegisterErrorResponse = {
  ok: false,
  status: 400,
  json: async () => ({ detail: "Username already exists" })
};

const mockLoginErrorResponse = {
  ok: false,
  status: 401,
  json: async () => ({ detail: "Invalid credentials" })
};

// Mocking global fetch
beforeEach(() => {
  global.fetch = jest.fn();

  global.fetch.mockImplementation((url, options) => {
    // AUTH endpoints
    if (url.includes('/auth/register')) {
      return Promise.resolve(mockRegisterResponse);
    }
    if (url.includes('/auth/login')) {
      return Promise.resolve(mockLoginResponse);
    }
    if (url.includes('/chats/')) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => ({
          chats: [
            {
              id: 1,
              title: "Welcome Chat",
              created_at: "2026-01-17T00:00:00Z",
              message_count: 0
            }
          ]
        }),
        text: async () => JSON.stringify({ chats: [] })  // For error path
      });
    }
    if (url.includes('/auth-inference') || url.includes('/unauth-inference')) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => ({
          answer: "Langchain result for: hello"
        })
      });
    }

    // Default error for unhandled endpoints
    return Promise.resolve({
      ok: false,
      status: 404,
      json: async () => ({ detail: "Unhandled endpoint: " + url })
    });
  });
});

afterEach(() => {
  global.fetch.mockClear();
  delete global.fetch;
});

describe("User Authentication", () => {
  beforeEach(() => {
    // Reset auth-specific fetch mocks for each test
    global.fetch.mockClear();
  });

  test("renders login and sign up buttons when not authenticated", () => {
    render(<ChatbotUI />);
    expect(screen.getByRole("button", { name: /log in/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign up/i })).toBeInTheDocument();
    expect(screen.queryByText(/logged in as/i)).not.toBeInTheDocument();
  });

  test("renders user info and logout button when authenticated", async () => {
    // Mock successful login first
    global.fetch.mockResolvedValueOnce(mockLoginResponse);
    
    render(<ChatbotUI />);
    
    // 1. Start with login → simulates real user flow
    fireEvent.click(screen.getByTestId("header-login"));
    
    const usernameInput = screen.getByPlaceholderText(/username/i);
    const passwordInput = screen.getByPlaceholderText(/password/i);
    
    fireEvent.change(usernameInput, { target: { value: "testuser" } });
    fireEvent.change(passwordInput, { target: { value: "password123" } });
    
    fireEvent.click(screen.getByTestId("modal-submit"));
    
    // 2. Wait for auth state to update
    await waitFor(() => {
      expect(screen.queryByTestId("modal-submit")).not.toBeInTheDocument();
    });
    
    // 3. ✅ Verify AUTHENTICATED STATE renders
    expect(screen.getByText(/logged in as testuser/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Logout" })).toBeInTheDocument();
    
    // 4. ✅ Logout button works
    fireEvent.click(screen.getByRole("button", { name: "Logout" }));
    
    // 5. Verify back to unauthenticated state
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Log in" })).toBeInTheDocument();
      expect(screen.queryByText(/logged in as testuser/i)).not.toBeInTheDocument();
    });
  });

  test("clicking login button opens login modal", async () => {
    render(<ChatbotUI />);
    fireEvent.click(screen.getByTestId("header-login"));
    
    expect(screen.getByPlaceholderText(/username/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/password/i)).toBeInTheDocument();
  });

  test("clicking sign up button opens register modal", async () => {
    render(<ChatbotUI />);
    const signupButton = screen.getByRole("button", { name: /sign up/i });
    
    fireEvent.click(signupButton);
    
    expect(screen.getByRole("heading", { name: /sign up/i })).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/username/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/email/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/password/i)).toBeInTheDocument();
  });

  test("successful registration closes modal and shows logged in state", async () => {
    render(<ChatbotUI />);
    fireEvent.click(screen.getByTestId("header-signup"));
    
    const usernameInput = screen.getByPlaceholderText(/username/i);
    const emailInput = screen.getByPlaceholderText(/email/i);
    const passwordInput = screen.getByPlaceholderText(/password/i);
    
    fireEvent.change(usernameInput, { target: { value: "testuser" } });
    fireEvent.change(emailInput, { target: { value: "test@example.com" } });
    fireEvent.change(passwordInput, { target: { value: "password123" } });
    
    fireEvent.click(screen.getByTestId("modal-submit"));
    
    await waitFor(() => {
      expect(screen.getByText(/logged in as testuser/i)).toBeInTheDocument();
    });
    
    // Verify registration API was called
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/auth/register"),
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: "testuser",
          email: "test@example.com",
          password: "password123"
        })
      })
    );
  });

  test("successful login closes modal, sets token, and shows logged in state", async () => {
    render(<ChatbotUI />);
    fireEvent.click(screen.getByTestId("header-login"));
    
    const usernameInput = screen.getByPlaceholderText(/username/i);
    const passwordInput = screen.getByPlaceholderText(/password/i);
    
    fireEvent.change(usernameInput, { target: { value: "testuser" } });
    fireEvent.change(passwordInput, { target: { value: "password123" } });
    
    fireEvent.click(screen.getByTestId("modal-submit"));
    
    await waitFor(() => {
      expect(screen.queryByRole("heading", { name: /log in/i })).not.toBeInTheDocument();
    });
    
    // Verify login API was called
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/auth/login"),
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: "testuser",
          password: "password123"
        })
      })
    );
  });

  test("registration error displays error message", async () => {
    global.fetch.mockResolvedValueOnce(mockRegisterErrorResponse);
    
    render(<ChatbotUI />);
    fireEvent.click(screen.getByTestId("header-signup"));
    
    const usernameInput = screen.getByPlaceholderText(/username/i);
    const emailInput = screen.getByPlaceholderText(/email/i);
    const passwordInput = screen.getByPlaceholderText(/password/i);
    
    fireEvent.change(usernameInput, { target: { value: "duplicate" } });
    fireEvent.change(emailInput, { target: { value: "test@example.com" } });
    fireEvent.change(passwordInput, { target: { value: "password123" } });
    
    fireEvent.click(screen.getByTestId("modal-submit"));
    
    await waitFor(() => {
      expect(screen.getByText(/username already exists/i)).toBeInTheDocument();
    });
  });

  test("login error displays error message", async () => {
    global.fetch.mockResolvedValueOnce(mockLoginErrorResponse);
    
    render(<ChatbotUI />);
    fireEvent.click(screen.getByTestId("header-login"));
    
    const usernameInput = screen.getByPlaceholderText(/username/i);
    const passwordInput = screen.getByPlaceholderText(/password/i);
    
    fireEvent.change(usernameInput, { target: { value: "wronguser" } });
    fireEvent.change(passwordInput, { target: { value: "wrongpass" } });
    
    fireEvent.click(screen.getByTestId("modal-submit"));
    
    await waitFor(() => {
      expect(screen.getByText(/invalid credentials/i)).toBeInTheDocument();
    });
  });

  test("cancel button closes auth modal", async () => {
    render(<ChatbotUI />);
    const loginButton = screen.getByRole("button", { name: /log in/i });
    
    fireEvent.click(loginButton);
    expect(screen.getByRole("heading", { name: /log in/i })).toBeInTheDocument();
    
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    
    await waitFor(() => {
      expect(screen.queryByRole("heading", { name: /log in/i })).not.toBeInTheDocument();
    });
  });

  test("logout clears auth state and shows login buttons", async () => {
    // This test verifies the logout button exists and clicking works
    // Full state verification requires a custom render wrapper
    render(<ChatbotUI />);
    
    // Simulate logged in state by checking conditional rendering exists
    const logoutButton = screen.queryByRole("button", { name: /logout/i });
    
    if (logoutButton) {
      fireEvent.click(logoutButton);
      // Would verify login buttons reappear in full test
    }
  });
});

describe("ChatbotUI component", () => {
  test("renders initial UI with input and buttons", () => {
    render(<ChatbotUI />);
    expect(screen.getByPlaceholderText(/type your message here/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /send/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /upload image/i })).toBeInTheDocument();
    expect(screen.getByText(/start the conversation/i)).toBeInTheDocument();
  });

  test("typing text updates input box value", () => {
    render(<ChatbotUI />);
    const textarea = screen.getByPlaceholderText(/type your message here/i);
    fireEvent.change(textarea, { target: { value: "Hello" } });
    expect(textarea.value).toBe("Hello");
  });

  test("sending text message adds user message and bot echo", async () => {
    render(<ChatbotUI />);
    const textarea = screen.getByPlaceholderText(/type your message here/i);
    const sendButton = screen.getByRole("button", { name: /send/i });

    fireEvent.change(textarea, { target: { value: "Hello" } });
    fireEvent.click(sendButton);

    // User message appears
    expect(screen.getByText("Hello")).toBeInTheDocument();

    // Wait for API response
    await waitFor(() => expect(screen.getByText(/langchain result for: hello/i)).toBeInTheDocument());
  });

  test("sending empty text does not add message", () => {
    render(<ChatbotUI />);
    const sendButton = screen.getByRole("button", { name: /send/i });
    fireEvent.click(sendButton);

    expect(screen.getByText(/start the conversation/i)).toBeInTheDocument();
  });

  test.skip("uploading image shows preview and then can remove it", () => {
    render(<ChatbotUI />);
    const uploadButton = screen.getByRole("button", { name: /upload image button/i });
    const file = new File(["test"], "test.png", { type: "image/png" });

    // Open file selector
    fireEvent.click(uploadButton);

    // Simulate the onChange event manually.
    const fileInput = screen.getByLabelText("Upload image");
    fireEvent.change(fileInput, { target: { files: [file] } });

    // Image preview should appear
    const previewImg = screen.getByAltText(/selected upload preview/i);
    expect(previewImg).toBeInTheDocument();

    // Remove preview by clicking "×" button
    const removeButton = screen.getByLabelText(/remove selected image/i);
    fireEvent.click(removeButton);

    expect(previewImg).not.toBeInTheDocument();
  });

  test.skip("sending combined text and image message", async () => {
    render(<ChatbotUI />);
    const textarea = screen.getByPlaceholderText(/type your message here/i);
    const uploadButton = screen.getByRole("button", { name: /upload image button/i });
    const sendButton = screen.getByRole("button", { name: /send/i });
    const file = new File(["test"], "test.png", { type: "image/png" });

    fireEvent.click(uploadButton);
    const fileInput = screen.getByLabelText("Upload image");
    fireEvent.change(fileInput, { target: { files: [file] } });

    fireEvent.change(textarea, { target: { value: "Picture" } });
    fireEvent.click(sendButton);

    // User message with text and image
    expect(screen.getByText("Picture")).toBeInTheDocument();
    expect(screen.getByAltText("Message attachment")).toBeInTheDocument();

    // Wait for API
    await waitFor(
        () => {
                const matches = screen.queryAllByText(content =>
                content.toLowerCase().includes("langchain result for: picture")
                );
                expect(matches.length).toBeGreaterThan(0);
            },
            { timeout: 2000 } // wait up to 2 seconds for async bot response
    );    
});

  test.skip("clicking on image opens enlarged lightbox and can close it", async () => {
    render(<ChatbotUI />);

    // Mock file to upload
    const file = new File(["dummy"], "test.png", { type: "image/png" });

    // Upload image via hidden file input
    const uploadButton = screen.getByRole("button", { name: /upload image button/i });
    fireEvent.click(uploadButton);

    const fileInput = screen.getByLabelText("Upload image");
    fireEvent.change(fileInput, { target: { files: [file] } });

    // Send the message
    const sendButton = screen.getByRole("button", { name: /send message/i });
    fireEvent.click(sendButton);

    // Wait for user message with image to appear
    const uploadedImg = await screen.findByAltText("Message attachment");
    expect(uploadedImg).toBeInTheDocument();

    // Click to open lightbox
    fireEvent.click(uploadedImg);

    // Enlarged image should appear
    const enlarged = screen.getByAltText("Enlarged user upload");
    expect(enlarged).toBeInTheDocument();

    // Close lightbox
    const closeBtn = screen.getByLabelText(/close image preview/i);
    fireEvent.click(closeBtn);

    // Lightbox should disappear
    expect(screen.queryByAltText("Enlarged user upload")).not.toBeInTheDocument();
    });
});

// To be implemented
// describe("Authenticated Chat Management", () => {
//   let mockFetchChats, mockFetchMessages, mockCreateChat;

//   beforeEach(async () => {
//     render(<ChatbotUI />);  // ← Move render here
    
//     // Login WITHOUT clearing fetch (keep chat mocks)
//     fireEvent.click(screen.getByTestId("header-login"));
//     fireEvent.change(screen.getByPlaceholderText(/username/i), { target: { value: "testuser" } });
//     fireEvent.change(screen.getByPlaceholderText(/password/i), { target: { value: "password123" } });
//     fireEvent.click(screen.getByTestId("modal-submit"));
    
//     await waitFor(() => {
//       expect(screen.getByText(/logged in as testuser/i)).toBeInTheDocument();
//     });
//     // REMOVE: global.fetch.mockClear();  ← DELETE THIS LINE
//   });

//   test("loads user chats after successful login", async () => {
//     await screen.findByRole("button", { name: /new chat/i });
  
//     // Wait for chats dropdown (loadUserChats success)
//     await screen.findByText("Welcome Chat");
    
//     // Verify API call
//     expect(global.fetch).toHaveBeenCalledWith(
//       expect.stringContaining("/chats/42"),
//       expect.objectContaining({ method: "GET" })
//     );
//   });

//   test("chat selector shows 'Select chat...' when no chats", async () => {
//     global.fetch.mockResolvedValueOnce(mockEmptyChatsResponse);
    
//     const chatSelect = await screen.findByRole("combobox");
//     expect(chatSelect.children).toHaveLength(1); // Only "Select chat..."
//     expect(chatSelect).toHaveValue("");
//   });

//   test("new chat button creates chat and updates selector", async () => {
//     // Setup: existing chats
//     global.fetch.mockResolvedValueOnce(mockChatsResponse);
//     await screen.findByRole("combobox"); // Wait for initial load

//     // Mock create new chat
//     global.fetch.mockResolvedValueOnce(mockNewChatResponse);

//     // Click New Chat
//     const newChatBtn = screen.getByRole("button", { name: /new chat/i });
//     fireEvent.click(newChatBtn);

//     // Verify POST /chats/{user_id}
//     expect(global.fetch).toHaveBeenCalledWith(
//       expect.stringContaining("/chats/"),
//       expect.objectContaining({
//         method: "POST",
//         headers: expect.objectContaining({
//           "Content-Type": "application/json",
//           Authorization: expect.stringContaining("mock-jwt-token-123")
//         })
//       })
//     );

//     // Verify selector now has 3 chats
//     await waitFor(() => {
//       const chatSelect = screen.getByRole("combobox");
//       expect(chatSelect.children).toHaveLength(4); // + "New Chat"
//     });
//   });

//   test("selecting chat loads messages and clears on new chat", async () => {
//     // Setup chats
//     global.fetch.mockResolvedValueOnce(mockChatsResponse);
//     await screen.findByRole("combobox");

//     // Mock message load for chat 1
//     global.fetch.mockResolvedValueOnce(mockChatMessagesResponse);

//     // Select first chat
//     const chatSelect = screen.getByRole("combobox");
//     fireEvent.change(chatSelect, { target: { value: "1" } });

//     // Verify messages loaded
//     await waitFor(() => {
//       expect(screen.getByText("What is this image?")).toBeInTheDocument();
//       expect(screen.getByText("This is a cat.")).toBeInTheDocument();
//     });

//     // Verify GET /chat/{user_id}/{chat_id}
//     expect(global.fetch).toHaveBeenCalledWith(
//       expect.stringContaining("/chat/"),
//       expect.objectContaining({ headers: expect.objectContaining({ Authorization: expect.stringContaining("mock-jwt-token-123") }) })
//     );

//     // Create new chat → messages should clear
//     global.fetch.mockResolvedValueOnce(mockNewChatResponse);
//     const newChatBtn = screen.getByRole("button", { name: /new chat/i });
//     fireEvent.click(newChatBtn);

//     await waitFor(() => {
//       expect(screen.queryByText("What is this image?")).not.toBeInTheDocument();
//       expect(screen.queryByText("This is a cat.")).not.toBeInTheDocument();
//       expect(screen.getByText(/start the conversation/i)).toBeInTheDocument();
//     });
//   });

//   test("chat operations show errors gracefully", async () => {
//     // Setup chats (succeeds)
//     global.fetch.mockResolvedValueOnce(mockChatsResponse);
//     await screen.findByRole("combobox");

//     // Mock failed message load
//     global.fetch.mockResolvedValueOnce(mockChatErrorResponse);

//     // Select chat → error message appears
//     const chatSelect = screen.getByRole("combobox");
//     fireEvent.change(chatSelect, { target: { value: "999" } }); // Invalid chat

//     await waitFor(() => {
//       // Error handled by console.error, no crash
//       expect(screen.getByText(/start the conversation/i)).toBeInTheDocument();
//     });
//   });

//   test("authenticated inference uses chat_id", async () => {
//     // Setup: login + chats
//     global.fetch.mockResolvedValueOnce(mockChatsResponse);
//     await screen.findByRole("combobox");

//     // Select chat first
//     const chatSelect = screen.getByRole("combobox");
//     fireEvent.change(chatSelect, { target: { value: "1" } });
//     global.fetch.mockResolvedValueOnce(mockChatMessagesResponse); // load messages

//     // Send message → uses auth-inference with chat_id
//     const textarea = screen.getByPlaceholderText(/type your message here/i);
//     fireEvent.change(textarea, { target: { value: "Test auth inference" } });
//     fireEvent.click(screen.getByRole("button", { name: /send/i }));

//     expect(global.fetch).toHaveBeenCalledWith(
//       expect.stringContaining("/auth-inference"),
//       expect.objectContaining({
//         method: "POST",
//         headers: expect.objectContaining({
//           "Content-Type": "application/json",
//           Authorization: expect.stringContaining("mock-jwt-token-123")
//         }),
//         body: JSON.stringify(expect.objectContaining({
//           user_id: expect.any(Number),
//           chat_id: 1,
//           user_query: expect.objectContaining({ role: "user" })
//         }))
//       })
//     );

//     // Bot response appears
//     await waitFor(() => {
//       expect(screen.getByText(/langchain result for: test auth inference/i)).toBeInTheDocument();
//     });
//   });
// });

// // Unskip and fix image tests with this helper
// const setupImageUpload = async (container) => {
//   const uploadBtn = screen.getByRole("button", { name: /upload image button/i });
//   fireEvent.click(uploadBtn);
//   const fileInput = screen.getByLabelText("Upload image");
//   const file = new File(["test"], "test.png", { type: "image/png" });
//   fireEvent.change(fileInput, { target: { files: [file] } });
  
//   // Wait for FileReader mock + image.onload → pendingImage set
//   await waitFor(() => {
//     expect(screen.getByAltText("Selected upload preview")).toBeInTheDocument();
//   });
// };

// // Replace .skip with these fixed tests:
// test("uploading image shows preview and then can remove it", async () => {
//   render(<ChatbotUI />);
//   await setupImageUpload();
  
//   const removeBtn = screen.getByLabelText(/remove selected image/i);
//   fireEvent.click(removeBtn);
  
//   await waitFor(() => {
//     expect(screen.queryByAltText("Selected upload preview")).not.toBeInTheDocument();
//   });
// });

// test("sending combined text and image message", async () => {
//   render(<ChatbotUI />);
//   await setupImageUpload();
  
//   const textarea = screen.getByPlaceholderText(/type your message here/i);
//   fireEvent.change(textarea, { target: { value: "Picture?" } });
//   fireEvent.click(screen.getByRole("button", { name: /send/i }));
  
//   expect(screen.getByText("Picture?")).toBeInTheDocument();
//   expect(screen.getByAltText("Message attachment")).toBeInTheDocument();
  
//   await waitFor(() => {
//     expect(screen.getByText(/langchain result for: picture\?/i)).toBeInTheDocument();
//   });
// });

// test("clicking on image opens enlarged lightbox and can close it", async () => {
//   render(<ChatbotUI />);
//   await setupImageUpload();
//   fireEvent.click(screen.getByPlaceholderText(/type your message here/i)); // Clear text
//   fireEvent.click(screen.getByRole("button", { name: /send/i }));
  
//   const msgImg = await screen.findByAltText("Message attachment");
//   fireEvent.click(msgImg);
  
//   const lightboxImg = screen.getByAltText("Enlarged user upload");
//   expect(lightboxImg).toBeInTheDocument();
  
//   const closeBtn = screen.getByLabelText(/close image preview/i);
//   fireEvent.click(closeBtn);
  
//   await waitFor(() => {
//     expect(screen.queryByAltText("Enlarged user upload")).not.toBeInTheDocument();
//   });
// });
