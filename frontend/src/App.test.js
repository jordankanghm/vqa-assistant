import { render, screen } from "@testing-library/react";
import App from "./App";

test("renders app header", () => {
  render(<App />);
  // Replace with a query that exists in your current App UI
  const headerElement = screen.getByText(/Visual Question Answering Assistant/i);
  expect(headerElement).toBeInTheDocument();
});
