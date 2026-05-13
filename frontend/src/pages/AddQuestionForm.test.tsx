/**
 * Tests for the AI difficulty suggestion feature inside AddQuestionForm.
 *
 * When a teacher finishes typing a question and moves focus away (blur),
 * the form calls /quizzes/questions/suggest-difficulty and, if AI is enabled,
 * auto-sets the difficulty dropdown and shows an "AI set" badge.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as apiModule from "../api";
import { AddQuestionForm } from "./TeacherQuizDetailPage";

vi.mock("../api", () => ({ api: vi.fn() }));

const mockApi = vi.mocked(apiModule.api);

function renderForm() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <AddQuestionForm quizId="test-quiz-id" />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  mockApi.mockReset();
});

describe("AddQuestionForm — AI difficulty suggestion", () => {
  it("renders the difficulty dropdown defaulting to Medium", () => {
    renderForm();
    const select = screen.getByRole("combobox", { name: /difficulty/i }) as HTMLSelectElement;
    expect(select.value).toBe("MEDIUM");
  });

  it("shows 'AI set' badge and updates dropdown after question text blur", async () => {
    const user = userEvent.setup();

    // suggest-difficulty returns HARD; add-question call returns a stub
    mockApi
      .mockResolvedValueOnce({ difficulty: "HARD", ai_used: true })
      .mockResolvedValue({ id: "q1", text: "", type: "MULTIPLE_CHOICE", difficulty: "HARD", points: 1, order_index: 0, quiz_id: "test-quiz-id", explanation: null, correct_text_answer: null, options: [] });

    renderForm();

    const textarea = screen.getByRole("textbox", { name: /question/i });
    await user.type(textarea, "What is the derivative of sin(x)?");
    await user.tab(); // triggers onBlur → fetchSuggestion

    await waitFor(() => {
      expect(screen.getByText("AI set")).toBeInTheDocument();
    });

    const select = screen.getByRole("combobox", { name: /difficulty/i }) as HTMLSelectElement;
    expect(select.value).toBe("HARD");
  });

  it("does not show 'AI set' badge when ai_used is false", async () => {
    const user = userEvent.setup();

    mockApi.mockResolvedValueOnce({ difficulty: "MEDIUM", ai_used: false });

    renderForm();
    const textarea = screen.getByRole("textbox", { name: /question/i });
    await user.type(textarea, "Name the capital of France.");
    await user.tab();

    // give it time to settle
    await waitFor(() => {
      expect(screen.queryByText("AI set")).not.toBeInTheDocument();
    });
  });

  it("clears 'AI set' badge when teacher manually changes difficulty", async () => {
    const user = userEvent.setup();

    mockApi.mockResolvedValueOnce({ difficulty: "HARD", ai_used: true });

    renderForm();
    const textarea = screen.getByRole("textbox", { name: /question/i });
    await user.type(textarea, "Explain the CAP theorem in distributed systems.");
    await user.tab();

    await waitFor(() => expect(screen.getByText("AI set")).toBeInTheDocument());

    // Teacher overrides the suggestion
    await user.selectOptions(screen.getByRole("combobox", { name: /difficulty/i }), "EASY");
    expect(screen.queryByText("AI set")).not.toBeInTheDocument();
  });
});
