import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { TeacherQuizCreatePage } from "./TeacherQuizCreatePage";

vi.mock("../api", () => ({ api: vi.fn().mockResolvedValue({}) }));

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <TeacherQuizCreatePage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("TeacherQuizCreatePage", () => {
  it("renders core form fields", () => {
    renderPage();
    expect(screen.getByText("Title")).toBeInTheDocument();
    expect(screen.getByText("Subject")).toBeInTheDocument();
    expect(screen.getByText(/duration/i)).toBeInTheDocument();
    expect(screen.getByText(/passing score/i)).toBeInTheDocument();
  });

  it("renders the schedule date field that triggers student notifications", () => {
    renderPage();
    expect(screen.getByText(/schedule date/i)).toBeInTheDocument();
    const dateInput = document.querySelector("input[type='datetime-local']");
    expect(dateInput).toBeInTheDocument();
  });

  it("renders adaptive difficulty toggle", () => {
    renderPage();
    expect(screen.getByText(/adaptive difficulty/i)).toBeInTheDocument();
    const checkbox = screen.getByRole("checkbox");
    expect(checkbox).toBeChecked(); // on by default
  });

  it("renders submit and cancel buttons", () => {
    renderPage();
    expect(screen.getByRole("button", { name: /create quiz/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /cancel/i })).toBeInTheDocument();
  });
});
