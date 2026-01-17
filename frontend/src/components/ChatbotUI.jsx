import React, { useState, useRef, useEffect } from "react";

const GATEWAY_URL = "http://localhost:8000"

const ChatMessage = ({ message, onImageClick }) => {
  // Extract text parts concatenated as text
  const textParts = message.content
    .filter(c => c.type === "text")
    .map(c => c.text)
    .join("\n");

  // Find first image URL or base64 data for display
  const imagePart = message.content.find(
    c => c.type === "image_url" || c.type === "image_base64"
  );

  // Determine image source if present
  const imageSrc = imagePart
    ? imagePart.type === "image_url"
      ? imagePart.image_url.url
      : imagePart.image_base64.base64
    : null;

  return (
    <div
      style={{
        maxWidth: "60%",
        marginBottom: 12,
        alignSelf: message.isUser ? "flex-end" : "flex-start",
        backgroundColor: message.isUser ? "#DCF8C6" : "#F1F0F0",
        borderRadius: 12,
        padding: "8px 12px",
        wordBreak: "break-word",
        cursor: imageSrc ? "pointer" : "default",
      }}
      onClick={() => imageSrc && onImageClick(imageSrc)}
      role="button"
      className={message.isUser ? "user-message" : "bot-message"}
      tabIndex={imageSrc ? 0 : -1}
      onKeyDown={(e) => {
        if (imageSrc && (e.key === "Enter" || e.key === " ")) {
          onImageClick(imageSrc);
        }
      }}
    >
      {textParts && (
        <div className="message-text" style={{ marginBottom: imageSrc ? 8 : 0 }}>
          {textParts}
        </div>
      )}
      {imageSrc && (
        <img
          src={imageSrc}
          alt="Message attachment"
          style={{ maxWidth: "100%", borderRadius: 8, pointerEvents: "none" }}
        />
      )}
      <div
        style={{
          fontSize: 10,
          color: "#555",
          marginTop: 4,
          textAlign: "right",
          opacity: 0.6,
        }}
      >
        {message.timestamp.toLocaleTimeString()}
      </div>
    </div>
  );
};

export default function ChatbotUI() {
  const [messages, setMessages] = useState([]);
  const [textInput, setTextInput] = useState("");
  const [pendingImage, setPendingImage] = useState(null);
  const [lightboxImage, setLightboxImage] = useState(null);
  const fileInputRef = useRef(null);
  const chatEndRef = useRef(null);

  // auth state
  const [user, setUsername] = useState(null); // Current logged-in username, e.g. { username: "testuser" }
  const [userId, setUserId] = useState(null);  // Current logged-in userId, e.g. 42
  const [currentChatId, setCurrentChatId] = useState(null);  // Current chatId, e.g. 1 (Welcome Chat)
  const [chats, setChats] = useState([]);  // Current chats, e.g. [{id: 1, title: "Welcome Chat"}, ...]
  const [token, setToken] = useState(null); // JWT access token for API calls, e.g. "eyJhb..."
  const [authOpen, setAuthOpen] = useState(false); // Auth modal visible? e.g. True
  const [authMode, setAuthMode] = useState("login"); // Login form or register form? e.g. "login" | "register"
  const [authForm, setAuthForm] = useState({ username: "", email: "", password: "" }); // Form input values, e.g. {username: "test", email: "test@test.com", password: "123"}
  const [authError, setAuthError] = useState(""); // Last auth error message, e.g. "Username already registered"

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const imageExtensions = [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg"];

  // Utility to find all valid image URLs in a text string
  function extractImageUrls(text) {
    const urlRegex = /(https?:\/\/[^\s]+)/g;
    const urls = [];
    let match;
    while ((match = urlRegex.exec(text)) !== null) {
      const url = match[1];
      // Check if URL ends like an image extension (case insensitive)
      if (imageExtensions.some(ext => url.toLowerCase().endsWith(ext))) {
        urls.push(url);
      }
    }
    return urls;
  }

  const handleSendMessage = async () => {
    if (!textInput.trim() && !pendingImage) return;

    let text = textInput.trim();
    // Extract all image URLs from the text and remove them from the text
    const imageUrls = extractImageUrls(text);
    imageUrls.forEach(url => {
      // Remove URL text from message text
      text = text.replace(url, "").trim();
    });

    // Prepare message: text and images from URLs + any pending image upload
    const images = [...imageUrls];
    if (pendingImage) {
      images.push(pendingImage);
    }

    // Compose new message
    const content = [];

    if (text) {
      content.push({ type: "text", text: text });
    }

    images.forEach(img => {
      if (img.startsWith("http://") || img.startsWith("https://")) {
        content.push({ type: "image_url", image_url: { url: img } });
      } else if (img.startsWith("data:image/")) {
        content.push({ type: "image_base64", image_base64: { base64: img } });
      }
    });

    const newMessage = {
      id: Date.now(),
      content: content,
      isUser: true,
      timestamp: new Date(),
    };

    // Append newMessage to messages
    setMessages(prev => [...prev, newMessage]);
    setTextInput("");
    setPendingImage(null);

    // Build chat history for API request
    const chatHistory = [];
    const combinedMessages = [...messages, newMessage];

    combinedMessages.forEach(msg => {
      if (msg.content && msg.content.length > 0) {
        chatHistory.push({
          role: msg.isUser ? "user" : "assistant",
          content: msg.content,
        });
      }
    });

    // Call API Gateway
    const lastUserContent = content;
    const lastUserMessage = {
      role: "user",
      content: lastUserContent
    };
    try {
      let res;
  
      if (!token) {
        // UNAUTH: send full chat history  
        res = await fetch(`${GATEWAY_URL}/unauth-inference`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ messages: chatHistory }),
        });
        
      } else if (userId && currentChatId) {
        // AUTH: send only latest user message + IDs
        res = await fetch(`${GATEWAY_URL}/auth-inference`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${token}`,
          },
          body: JSON.stringify({
            user_query: lastUserMessage,
            user_id: userId,
            chat_id: currentChatId,
          }),
        });
        
      } else {
        throw new Error("Missing userId or currentChatId for authenticated inference");
      }
      
      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        throw new Error(errBody.detail || `Inference failed: ${res.status}`);
      }
      
      const reply = await res.json();
      const botMessage = {
        id: Date.now() + 1,
        content: [{ type: "text", text: reply.answer }],
        isUser: false,
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, botMessage]);
    } catch (err) {
      const botMessage = {
        id: Date.now() + 1,
        content: [{ type: "text", text: "Inference failed: " + err.message }],
        image: null,
        isUser: false,
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, botMessage]);
    }
  };

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      alert("Please upload a valid image file.");
      return;
    }

    const reader = new FileReader();

    reader.onload = (ev) => {
      const img = new Image();

      // Downscale large images to max 512px width/height for cost-efficiency
      img.onload = () => {
        const maxDimension = 512; // max width or height
        let { width, height } = img;

        // Calculate new size preserving aspect ratio
        if (width > height) {
          if (width > maxDimension) {
            height = (height * maxDimension) / width;
            width = maxDimension;
          }
        } else {
          if (height > maxDimension) {
            width = (width * maxDimension) / height;
            height = maxDimension;
          }
        }

        // Create canvas to resize image
        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(img, 0, 0, width, height);

        // Get base64 of resized image (JPEG format, 0.7 quality)
        const resizedBase64 = canvas.toDataURL("image/jpeg", 0.7);

        setPendingImage(resizedBase64);
      };
      img.src = ev.target.result;
    };

    reader.readAsDataURL(file);
    e.target.value = null;
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const removePendingImage = () => {
    setPendingImage(null);
  };

  const closeLightbox = () => {
    setLightboxImage(null);
  };

  // ---------- Auth handlers ----------

  const openAuth = (mode) => {
    setAuthMode(mode);
    setAuthForm({ username: "", email: "", password: "" });
    setAuthError("");
    setAuthOpen(true);
  };

  const closeAuth = () => {
    setAuthOpen(false);
    setAuthError("");
  };

  const handleAuthChange = (e) => {
    const { name, value } = e.target;
    setAuthForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setAuthError("");
    try {
      const resp = await fetch(`${GATEWAY_URL}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: authForm.username,
          email: authForm.email,
          password: authForm.password,
        }),
      });
      if (!resp.ok) {
        const errBody = await resp.json().catch(() => ({}));
        throw new Error(errBody.detail || "Registration failed");
      }

      const res = await fetch(`${GATEWAY_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: authForm.username,
          password: authForm.password,
        }),
      });
      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        throw new Error(errBody.detail || "Login failed");
      }
      // Registration success: auto-login optional; here just close modal
      const data = await res.json();
      setToken(data.access_token)
      setUsername({ username: authForm.username });
      setUserId(data.user_id);
      closeAuth();

      // Auto-load user's chats
      await loadUserChats(data.user_id, data.access_token);
    } catch (err) {
      setAuthError(err.message);
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setAuthError("");
    try {
      const res = await fetch(`${GATEWAY_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: authForm.username,
          password: authForm.password,
        }),
      });
      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        throw new Error(errBody.detail || "Login failed");
      }
      const data = await res.json();
      setToken(data.access_token);
      setUsername({ username: authForm.username });
      setUserId(data.user_id)
      closeAuth();

      // Auto-load user's chats
      await loadUserChats(data.user_id, data.access_token);
    } catch (err) {
      setAuthError(err.message);
    }
  };

  const handleLogout = () => {
    setUsername(null);
    setToken(null);
  };

  const loadUserChats = async (userId, token) => {
    try {
      const res = await fetch(`${GATEWAY_URL}/chats/${userId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        console.error("Failed to load chats:", await res.text());
        setChats([]);  // Reset to empty array on error
        return;
      }
      const data = await res.json();
      const chatsList = data.chats;
      setChats(data.chats);

      const defaultChatId = chatsList[0].id;
      setCurrentChatId(defaultChatId);
      
    } catch (err) {
      console.error("loadUserChats error:", err);
    }
  };

  const chatSelectOnChange = async (e) => {
    const chatId = Number(e.target.value);
    if (!chatId) return;
    
    if (!userId || !token) {
      console.error('❌ Auth missing at chat select');
      return;
    }
    
    setCurrentChatId(chatId);
    await loadChatMessages(chatId);
  };

  const createNewChat = async () => {
    if (!userId || !token) return;
    
    try {
      const res = await fetch(`${GATEWAY_URL}/chats/${userId}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`,
        }
      });
      
      if (!res.ok) {
        console.error("Failed to create chat:", await res.text());
        return;
      }
      
      const newChat = await res.json();
      setChats(prev => [...prev, newChat]);
      setCurrentChatId(newChat.id);
      setMessages([]); // Clear messages for new chat
    } catch (err) {
      console.error("createNewChat error:", err);
    }
  };

  const loadChatMessages = async (chatId) => {
    if (!userId || !token) {
      console.error("❌ Missing auth for loadChatMessages", { userId: !!userId, token: !!token });
      return;
    }
    
    try {
      const res = await fetch(`${GATEWAY_URL}/chat/${userId}/${chatId}`, {
        headers: { "Authorization": `Bearer ${token}` },
      });
      
      
      if (!res.ok) {
        console.error("Messages failed:", res.status, await res.text());
        return;
      }
      
      const data = await res.json();
      const messages = data.messages;
      
      const frontendMessages = messages.map(msg => ({
        id: msg.id || Date.now() + Math.random(),
        content: msg.content || [{ type: "text", text: msg.text || msg.content || "No content" }],
        isUser: msg.role === "user",
        timestamp: new Date(msg.created_at || msg.timestamp || Date.now()),
      }));
      
      setMessages(frontendMessages);
    } catch (err) {
      console.error("loadChatMessages error:", err);
    }
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        maxWidth: 600,
        margin: "0 auto",
        border: "1px solid #ddd",
        borderRadius: 8,
        overflow: "hidden",
        fontFamily: "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
      }}
    >
      <header
        style={{
          backgroundColor: "#007bff",
          color: "white",
          padding: 16,
          fontSize: 18,
          fontWeight: "bold",
          textAlign: "center",
        }}
      >
        <span>Visual Question Answering Assistant</span>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {user ? (
            <>
              <span style={{ fontSize: 12 }}>Logged in as {user.username}</span>
              <button
                onClick={handleLogout}
                style={{
                  backgroundColor: "transparent",
                  border: "1px solid #fff",
                  color: "#fff",
                  borderRadius: 16,
                  padding: "4px 10px",
                  fontSize: 12,
                  cursor: "pointer",
                }}
              >
                Logout
              </button>
            </>
          ) : (
            <>
              <button
                data-testid="header-login"
                onClick={() => openAuth("login")}
                style={{
                  backgroundColor: "transparent",
                  border: "1px solid #fff",
                  color: "#fff",
                  borderRadius: 16,
                  padding: "4px 10px",
                  fontSize: 12,
                  cursor: "pointer",
                }}
              >
                Log in
              </button>
              <button
                data-testid="header-signup"
                onClick={() => openAuth("register")}
                style={{
                  backgroundColor: "#28a745",
                  border: "none",
                  color: "#fff",
                  borderRadius: 16,
                  padding: "4px 10px",
                  fontSize: 12,
                  cursor: "pointer",
                }}
              >
                Sign up
              </button>
            </>
          )}
          {user && (
            <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
              <button
                onClick={createNewChat}
                style={{
                  backgroundColor: "#28a745",
                  border: "none",
                  color: "white",
                  borderRadius: 16,
                  padding: "4px 10px",
                  fontSize: 12,
                  cursor: "pointer",
                }}
                disabled={!token}
              >
                + New Chat
              </button>
              {chats.length > 0 && (
                <select 
                  value={currentChatId || ''} 
                  onChange={chatSelectOnChange}
                  style={{ padding: '4px 8px', fontSize: 12 }}
                >
                  <option value="">Select chat...</option>
                  {chats.map(chat => (
                    <option key={chat.id} value={chat.id}>
                      {chat.title || `Chat ${chat.id}`}
                    </option>
                  ))}
                </select>
              )}
            </div>
          )}
        </div>
      </header>

      <main
        style={{
          flexGrow: 1,
          overflowY: "auto",
          padding: 16,
          display: "flex",
          flexDirection: "column",
        }}
      >
        {messages.length === 0 && (
          <div style={{ textAlign: "center", color: "#666", marginTop: 40 }}>
            Start the conversation by typing a message or uploading an image.
          </div>
        )}
        {messages.map((msg) => (
          <ChatMessage key={msg.id} message={msg} onImageClick={setLightboxImage} />
        ))}
        <div ref={chatEndRef} />
      </main>

      <footer
        style={{
          padding: 12,
          borderTop: "1px solid #ccc",
          display: "flex",
          flexDirection: "column",
          gap: 8,
          backgroundColor: "#fafafa",
        }}
      >
        {pendingImage && (
          <div
            style={{
              position: "relative",
              maxWidth: "60%",
              alignSelf: "flex-end",
              borderRadius: 8,
              overflow: "hidden",
            }}
          >
            <img
              src={pendingImage}
              alt="Selected upload preview"
              style={{ width: "100%", borderRadius: 8 }}
            />
            <button
              onClick={removePendingImage}
              style={{
                position: "absolute",
                top: 4,
                right: 4,
                backgroundColor: "rgba(0,0,0,0.5)",
                color: "white",
                border: "none",
                borderRadius: "50%",
                width: 24,
                height: 24,
                cursor: "pointer",
              }}
              aria-label="Remove selected image"
            >
              &times;
            </button>
          </div>
        )}
        <div style={{ display: "flex", gap: 8 }}>
          <textarea
            aria-label="Chat input text"
            rows={1}
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            placeholder="Type your message here..."
            onKeyDown={handleKeyDown}
            style={{
              flexGrow: 1,
              borderRadius: 20,
              border: "1px solid #ccc",
              padding: 8,
              resize: "none",
              fontSize: 14,
              fontFamily: "inherit",
            }}
          />
          <button
            onClick={handleSendMessage}
            style={{
              backgroundColor: "#007bff",
              color: "white",
              border: "none",
              borderRadius: 20,
              padding: "8px 16px",
              cursor: "pointer",
              fontWeight: "bold",
            }}
            aria-label="Send message"
          >
            Send
          </button>
          <input
            type="file"
            accept="image/*"
            ref={fileInputRef}
            onChange={handleFileChange}
            style={{ display: "none" }}
            aria-label="Upload image"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            style={{
              backgroundColor: "#28a745",
              border: "none",
              borderRadius: 20,
              color: "white",
              padding: "8px 12px",
              cursor: "pointer",
              fontWeight: "bold",
            }}
            aria-label="Upload image button"
          >
            Upload Image
          </button>
        </div>
      </footer>

      {lightboxImage && (
        <div
          onClick={closeLightbox}
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(0,0,0,0.8)",
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            zIndex: 9999,
            cursor: "pointer",
          }}
        >
          <img
            src={lightboxImage}
            alt="Enlarged user upload"
            onClick={(e) => e.stopPropagation()} // prevent closing when clicking image itself
            style={{
              maxWidth: "90%",
              maxHeight: "90%",
              borderRadius: 12,
              boxShadow: "0 0 20px rgba(255,255,255,0.3)",
            }}
          />
          <button
            onClick={closeLightbox}
            aria-label="Close image preview"
            style={{
              position: "fixed",
              top: 20,
              right: 20,
              backgroundColor: "rgba(0,0,0,0.6)",
              color: "white",
              border: "none",
              borderRadius: "50%",
              width: 36,
              height: 36,
              fontSize: 24,
              cursor: "pointer",
            }}
          >
            &times;
          </button>
        </div>
      )}

      {authOpen && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(0,0,0,0.4)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 10000,
          }}
        >
          <div
            style={{
              backgroundColor: "#fff",
              padding: 20,
              borderRadius: 8,
              minWidth: 280,
              maxWidth: 360,
              boxShadow: "0 0 12px rgba(0,0,0,0.3)",
            }}
          >
            <h3 style={{ marginTop: 0, marginBottom: 12 }}>
              {authMode === "login" ? "Log in" : "Sign up"}
            </h3>
            <form onSubmit={authMode === "login" ? handleLogin : handleRegister}>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <input
                  name="username"
                  value={authForm.username}
                  onChange={handleAuthChange}
                  placeholder="Username"
                  required
                  style={{ padding: 6, fontSize: 14 }}
                />
                {authMode === "register" && (
                  <input
                    name="email"
                    type="email"
                    value={authForm.email}
                    onChange={handleAuthChange}
                    placeholder="Email"
                    required
                    style={{ padding: 6, fontSize: 14 }}
                  />
                )}
                <input
                  name="password"
                  type="password"
                  value={authForm.password}
                  onChange={handleAuthChange}
                  placeholder="Password"
                  required
                  style={{ padding: 6, fontSize: 14 }}
                />
              </div>
              {authError && (
                <div style={{ color: "red", marginTop: 8, fontSize: 12 }}>
                  {authError}
                </div>
              )}
              <div
                style={{
                  marginTop: 12,
                  display: "flex",
                  justifyContent: "flex-end",
                  gap: 8,
                }}
              >
                <button
                  type="button"
                  onClick={closeAuth}
                  style={{
                    border: "1px solid #ccc",
                    backgroundColor: "transparent",
                    borderRadius: 4,
                    padding: "4px 10px",
                    cursor: "pointer",
                  }}
                >
                  Cancel
                </button>
                <button
                  data-testid="modal-submit"
                  type="submit"
                  style={{
                    backgroundColor: "#007bff",
                    color: "#fff",
                    border: "none",
                    borderRadius: 4,
                    padding: "4px 12px",
                    cursor: "pointer",
                  }}
                >
                  {authMode === "login" ? "Log in" : "Sign up"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
