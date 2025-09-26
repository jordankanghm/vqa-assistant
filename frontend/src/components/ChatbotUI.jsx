import React, { useState, useRef, useEffect } from "react";

const ChatMessage = ({ message, onImageClick }) => {
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
        cursor: message.image ? "pointer" : "default",
      }}

      // If message has image, clicking anywhere on the message triggers enlarged view
      onClick={() => message.image && onImageClick(message.image)}
      role="button"
      className={message.isUser ? "user-message" : "bot-message"}
      tabIndex={message.image ? 0 : -1}
      onKeyDown={(e) => {
        if (message.image && (e.key === 'Enter' || e.key === ' ')) {
          onImageClick(message.image);
        }
      }}
    >
      {message.text && (
        <div className="message-text" style={{ marginBottom: message.image ? 8 : 0 }}>
          {message.text}
        </div>
      )}
      {message.image && (
        <img
          src={message.image}
          alt="User upload"
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

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSendMessage = async () => {
    if (!textInput.trim() && !pendingImage) return;

    let text = textInput.trim();
    let imageUrl = null;

    // Regex to find [Image Link: <url>] anywhere in the text
    const imageLinkRegex = /\[Image Link:\s*(\S+)\]/i;
    const match = text.match(imageLinkRegex);

    if (match) {
      const url = match[1];
      // Only accept http or https schemes for image extraction
      if (/^https?:\/\//i.test(url)) {
        imageUrl = url;
      }
      // Remove the entire [Image Link: url] substring regardless of validity
      text = text.replace(imageLinkRegex, "").trim();
    }
    
    // Use this text and extracted imageUrl for your message content
    const newMessage = {
      id: Date.now(),
      text: text || null,
      image: imageUrl || pendingImage || null,
      isUser: true,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, newMessage]);
    setTextInput("");
    setPendingImage(null);

    // Build chat history
    const chatHistory = [];

    messages.forEach(msg => {
      if (msg.text || msg.image) {
        const content = [];
        if (msg.text) {
          content.push({ type: "text", text: msg.text });
        }
        if (msg.image) {
          if (msg.image.startsWith("http://") || msg.image.startsWith("https://")) {
            content.push({ type: "image_url", image_url: { url: msg.image } });
          } else {
            content.push({ type: "image_base64", image_base64: { base64: msg.image } });
          }
        }
        chatHistory.push({
          role: msg.isUser ? "user" : "assistant",
          content: content,
        });
      }
    });

    // Include the new user message as well since messages state update is async
    if (newMessage.text || newMessage.image) {
      const content = [];
      if (newMessage.text) content.push({ type: "text", text: newMessage.text });
      if (newMessage.image) content.push({ type: "image_url", image_url: { url: newMessage.image } });
      chatHistory.push({
        role: "user",
        content: content,
      });
    }

    console.log(JSON.stringify({
          messages: chatHistory,
        }))
    // Call API Gateway
    try {
      const res = await fetch("http://localhost:8000/inference", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: chatHistory,
        }),
      });
      const reply = await res.json();

      const botMessage = {
        id: Date.now() + 1,
        text: reply.answer,
        isUser: false,
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, botMessage]);
    } catch (err) {
      const botMessage = {
        id: Date.now() + 1,
        text: "Inference failed: " + err.message,
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
      setPendingImage(ev.target.result);
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
        Visual Question Answering Assistant
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
    </div>
  );
}
