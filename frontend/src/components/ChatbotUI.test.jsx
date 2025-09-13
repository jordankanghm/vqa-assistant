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

    // Wait for bot echo to appear
    await waitFor(() => expect(screen.getByText(/echo: hello/i)).toBeInTheDocument());
  });

  test("sending empty text does not add message", () => {
    render(<ChatbotUI />);
    const sendButton = screen.getByRole("button", { name: /send/i });
    fireEvent.click(sendButton);

    expect(screen.getByText(/start the conversation/i)).toBeInTheDocument();
  });

  test("uploading image shows preview and then can remove it", () => {
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

  test("sending combined text and image message", async () => {
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
    expect(screen.getByAltText("User upload")).toBeInTheDocument();

    // Wait for bot echo
    await waitFor(
        () => {
                const matches = screen.queryAllByText(content =>
                content.toLowerCase().includes("echo: picture")
                );
                expect(matches.length).toBeGreaterThan(0);
            },
            { timeout: 2000 } // wait up to 2 seconds for async bot response
    );    
});

  test("clicking on image opens enlarged lightbox and can close it", async () => {
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
    const uploadedImg = await screen.findByAltText("User upload");
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
