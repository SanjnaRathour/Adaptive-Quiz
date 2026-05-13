import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "../api";
import type {
  Difficulty,
  DifficultyHintResponse,
  QuestionCreatePayload,
  QuestionTeacherRead,
  QuestionType,
  QuizSummary,
} from "../api";

export function TeacherQuizDetailPage() {
  const { quizId } = useParams<{ quizId: string }>();
  const queryClient = useQueryClient();

  const { data: quiz } = useQuery({
    queryKey: ["quiz", quizId],
    queryFn: () => api<QuizSummary>(`/quizzes/${quizId}`),
    enabled: !!quizId,
  });
  const { data: questions } = useQuery({
    queryKey: ["quiz", quizId, "questions"],
    queryFn: () =>
      api<QuestionTeacherRead[]>(`/quizzes/${quizId}/questions`),
    enabled: !!quizId,
  });

  const publish = useMutation({
    mutationFn: () =>
      api<QuizSummary>(`/quizzes/${quizId}/publish`, { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["quiz", quizId] });
      queryClient.invalidateQueries({ queryKey: ["quizzes"] });
      queryClient.invalidateQueries({ queryKey: ["teacher-overview"] });
    },
  });

  const deleteQuestion = useMutation({
    mutationFn: (questionId: string) =>
      api<void>(`/quizzes/questions/${questionId}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["quiz", quizId, "questions"] });
      queryClient.invalidateQueries({ queryKey: ["quiz", quizId] });
    },
  });

  if (!quiz) return <p className="text-slate-500">Loading quiz…</p>;

  return (
    <div className="space-y-6">
      <Link
        to="/teacher"
        className="text-sm text-slate-600 hover:text-slate-900"
      >
        ← Back to dashboard
      </Link>

      <header className="bg-white border border-slate-200 rounded-lg p-5">
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-xl font-semibold text-slate-900">{quiz.title}</h2>
            <p className="text-sm text-slate-500 mt-1">
              {quiz.subject} · {quiz.duration_minutes} min · pass{" "}
              {quiz.passing_score}% ·{" "}
              {quiz.is_adaptive ? "adaptive" : "linear"}
            </p>
            {quiz.description && (
              <p className="text-sm text-slate-700 mt-2">{quiz.description}</p>
            )}
          </div>
          <div className="flex sm:flex-col items-center sm:items-end gap-2">
            <span
              className={`text-xs px-2 py-0.5 rounded ${
                quiz.is_published
                  ? "bg-emerald-100 text-emerald-700"
                  : "bg-slate-100 text-slate-600"
              }`}
            >
              {quiz.is_published ? "Published" : "Draft"}
            </span>
            {!quiz.is_published && (
              <button
                onClick={() => publish.mutate()}
                disabled={
                  publish.isPending ||
                  !questions ||
                  questions.length === 0
                }
                className="text-sm bg-indigo-600 text-white rounded-lg px-3 py-1.5 hover:bg-indigo-700 disabled:bg-indigo-300 disabled:cursor-not-allowed"
                title={
                  questions && questions.length === 0
                    ? "Add at least one question first"
                    : ""
                }
              >
                {publish.isPending ? "Publishing…" : "Publish"}
              </button>
            )}
          </div>
        </div>
      </header>

      <section>
        <h3 className="font-semibold text-slate-900 mb-3">
          Questions ({questions?.length ?? 0})
        </h3>
        {questions && questions.length > 0 && (
          <ul className="space-y-2 mb-4">
            {questions.map((q, idx) => (
              <li
                key={q.id}
                className="bg-white border border-slate-200 rounded-lg p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1">
                    <p className="text-sm text-slate-500 mb-1">
                      Q{idx + 1} · {q.type.replace("_", " ")} · {q.difficulty}{" "}
                      · {q.points} pt{q.points === 1 ? "" : "s"}
                    </p>
                    <p className="font-medium text-slate-900">{q.text}</p>
                    {q.options.length > 0 && (
                      <ul className="mt-2 space-y-0.5 text-sm">
                        {q.options.map((o) => (
                          <li
                            key={o.id}
                            className={
                              o.is_correct
                                ? "text-emerald-700"
                                : "text-slate-600"
                            }
                          >
                            {o.is_correct ? "✓" : "·"} {o.text}
                          </li>
                        ))}
                      </ul>
                    )}
                    {q.correct_text_answer && (
                      <p className="mt-2 text-sm text-emerald-700">
                        ✓ {q.correct_text_answer}
                      </p>
                    )}
                  </div>
                  <button
                    onClick={() => {
                      if (confirm("Delete this question?"))
                        deleteQuestion.mutate(q.id);
                    }}
                    className="text-sm text-rose-600 hover:text-rose-800"
                  >
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}

        {quiz.is_published && (
          <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-3">
            Heads up: this quiz is published. New questions you add will appear
            for any students still mid-attempt, and deleting a question that
            has already been answered will remove those answers from analytics.
          </p>
        )}
        <AddQuestionForm quizId={quiz.id} />
      </section>
    </div>
  );
}

export function AddQuestionForm({ quizId }: { quizId: string }) {
  const queryClient = useQueryClient();
  const [type, setType] = useState<QuestionType>("MULTIPLE_CHOICE");
  const [text, setText] = useState("");
  const [difficulty, setDifficulty] = useState<Difficulty>("MEDIUM");
  const [points, setPoints] = useState(1);
  const [explanation, setExplanation] = useState("");
  const [shortAnswer, setShortAnswer] = useState("");
  const [options, setOptions] = useState<
    { text: string; is_correct: boolean }[]
  >([
    { text: "", is_correct: true },
    { text: "", is_correct: false },
    { text: "", is_correct: false },
    { text: "", is_correct: false },
  ]);
  const [aiSuggestion, setAiSuggestion] = useState<Difficulty | null>(null);
  const [isSuggesting, setIsSuggesting] = useState(false);

  const fetchSuggestion = async (questionText: string) => {
    if (questionText.trim().length < 2) return;
    setIsSuggesting(true);
    try {
      const hint = await api<DifficultyHintResponse>(
        "/quizzes/questions/suggest-difficulty",
        { method: "POST", json: { text: questionText.trim() } },
      );
      if (hint.ai_used) {
        setAiSuggestion(hint.difficulty);
        setDifficulty(hint.difficulty);
      }
    } catch {
      // silently ignore — teacher still has the manual dropdown
    } finally {
      setIsSuggesting(false);
    }
  };

  const reset = () => {
    setText("");
    setExplanation("");
    setShortAnswer("");
    setPoints(1);
    setDifficulty("MEDIUM");
    setAiSuggestion(null);
    setOptions([
      { text: "", is_correct: true },
      { text: "", is_correct: false },
      { text: "", is_correct: false },
      { text: "", is_correct: false },
    ]);
  };

  const setType_ = (t: QuestionType) => {
    setType(t);
    if (t === "TRUE_FALSE") {
      setOptions([
        { text: "True", is_correct: true },
        { text: "False", is_correct: false },
      ]);
    } else if (t === "MULTIPLE_CHOICE") {
      setOptions([
        { text: "", is_correct: true },
        { text: "", is_correct: false },
        { text: "", is_correct: false },
        { text: "", is_correct: false },
      ]);
    } else {
      setOptions([]);
    }
  };

  const addOption = () =>
    setOptions((prev) => [...prev, { text: "", is_correct: false }]);

  const updateOption = (
    idx: number,
    patch: Partial<{ text: string; is_correct: boolean }>,
  ) => {
    setOptions((prev) =>
      prev.map((o, i) => (i === idx ? { ...o, ...patch } : o)),
    );
  };

  const setCorrect = (idx: number) => {
    setOptions((prev) =>
      prev.map((o, i) => ({ ...o, is_correct: i === idx })),
    );
  };

  const removeOption = (idx: number) =>
    setOptions((prev) => prev.filter((_, i) => i !== idx));

  const save = useMutation({
    mutationFn: (payload: QuestionCreatePayload) =>
      api<QuestionTeacherRead>(`/quizzes/${quizId}/questions`, {
        method: "POST",
        json: payload,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["quiz", quizId, "questions"] });
      queryClient.invalidateQueries({ queryKey: ["quiz", quizId] });
      reset();
    },
  });

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const payload: QuestionCreatePayload = {
      text: text.trim(),
      type,
      difficulty,
      points,
      explanation: explanation.trim() || null,
      correct_text_answer:
        type === "SHORT_ANSWER" ? shortAnswer.trim() : null,
      options:
        type === "SHORT_ANSWER"
          ? []
          : options
              .map((o, i) => ({
                text: o.text.trim(),
                is_correct: o.is_correct,
                order_index: i,
              }))
              .filter((o) => o.text.length > 0),
    };
    save.mutate(payload);
  };

  return (
    <form
      onSubmit={onSubmit}
      className="bg-white border border-slate-200 rounded-lg p-5 space-y-4"
    >
      <h4 className="font-medium text-slate-900">Add a question</h4>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
        <label className="block">
          <span className="text-sm text-slate-700">Type</span>
          <select
            className="mt-1 w-full rounded border border-slate-300 px-2 py-2 text-sm"
            value={type}
            onChange={(e) => setType_(e.target.value as QuestionType)}
          >
            <option value="MULTIPLE_CHOICE">Multiple choice</option>
            <option value="TRUE_FALSE">True / False</option>
            <option value="SHORT_ANSWER">Short answer</option>
          </select>
        </label>
        <label className="block">
          <span className="text-sm text-slate-700 flex items-center gap-2">
            Difficulty
            {isSuggesting && (
              <span className="text-xs text-indigo-500 animate-pulse">AI thinking…</span>
            )}
            {!isSuggesting && aiSuggestion && (
              <span className="text-xs bg-indigo-100 text-indigo-700 px-1.5 py-0.5 rounded">
                AI set
              </span>
            )}
          </span>
          <select
            className="mt-1 w-full rounded border border-slate-300 px-2 py-2 text-sm"
            value={difficulty}
            onChange={(e) => {
              setDifficulty(e.target.value as Difficulty);
              setAiSuggestion(null);
            }}
          >
            <option value="EASY">Easy</option>
            <option value="MEDIUM">Medium</option>
            <option value="HARD">Hard</option>
          </select>
        </label>
        <label className="block">
          <span className="text-sm text-slate-700">Points</span>
          <input
            type="number"
            min={1}
            max={100}
            className="mt-1 w-full rounded border border-slate-300 px-2 py-2 text-sm"
            value={points}
            onChange={(e) => setPoints(Number(e.target.value))}
          />
        </label>
      </div>

      <label className="block">
        <span className="text-sm text-slate-700">Question</span>
        <textarea
          className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
          rows={2}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onBlur={(e) => fetchSuggestion(e.target.value)}
          required
        />
      </label>

      {type === "SHORT_ANSWER" ? (
        <label className="block">
          <span className="text-sm text-slate-700">Correct answer</span>
          <input
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
            value={shortAnswer}
            onChange={(e) => setShortAnswer(e.target.value)}
            required
          />
          <span className="text-xs text-slate-500 mt-1 block">
            Matched case-insensitively, trimmed.
          </span>
        </label>
      ) : (
        <div>
          <span className="text-sm text-slate-700">
            Options (mark the correct one)
          </span>
          <ul className="mt-2 space-y-2">
            {options.map((o, i) => (
              <li key={i} className="flex items-center gap-2">
                <input
                  type="radio"
                  name="correct"
                  checked={o.is_correct}
                  onChange={() => setCorrect(i)}
                />
                <input
                  className="flex-1 rounded border border-slate-300 px-2 py-1.5 text-sm"
                  placeholder={`Option ${i + 1}`}
                  value={o.text}
                  onChange={(e) =>
                    updateOption(i, { text: e.target.value })
                  }
                  required={i < 2 || type === "TRUE_FALSE"}
                  disabled={type === "TRUE_FALSE"}
                />
                {type === "MULTIPLE_CHOICE" && options.length > 2 && (
                  <button
                    type="button"
                    onClick={() => removeOption(i)}
                    className="text-sm text-slate-500 hover:text-rose-600"
                  >
                    ✕
                  </button>
                )}
              </li>
            ))}
          </ul>
          {type === "MULTIPLE_CHOICE" && (
            <button
              type="button"
              onClick={addOption}
              className="mt-2 text-sm text-slate-700 hover:text-slate-900"
            >
              + Add option
            </button>
          )}
        </div>
      )}

      <label className="block">
        <span className="text-sm text-slate-700">
          Explanation <span className="text-slate-400">(optional)</span>
        </span>
        <textarea
          className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
          rows={2}
          value={explanation}
          onChange={(e) => setExplanation(e.target.value)}
          placeholder="Shown to students with their results"
        />
      </label>

      {save.isError && (
        <p className="text-sm text-rose-600">
          {(save.error as Error)?.message ?? "Failed to add question"}
        </p>
      )}

      <button
        type="submit"
        disabled={save.isPending}
        className="bg-indigo-600 text-white rounded-lg px-4 py-2 hover:bg-indigo-700 disabled:bg-indigo-300 disabled:cursor-not-allowed"
      >
        {save.isPending ? "Adding…" : "Add question"}
      </button>
    </form>
  );
}
