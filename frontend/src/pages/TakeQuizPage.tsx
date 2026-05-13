import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { api } from "../api";
import type {
  AttemptQuestionItem,
  AttemptRead,
  Difficulty,
  NextQuestionResponse,
  PaginatedAttempts,
  QuestionStudentRead,
  QuizSummary,
} from "../api";
import { ConfirmModal } from "../components/ConfirmModal";

const OPTION_LETTERS = ["A", "B", "C", "D", "E", "F"];
const FEEDBACK_MS = 1100;

// ---------------------------------------------------------------------------
// Top-level page: load attempt + quiz, branch by quiz.is_adaptive.
// ---------------------------------------------------------------------------

function useCountdown(attempt: AttemptRead | null, durationMinutes: number | undefined) {
  const [secsLeft, setSecsLeft] = useState<number | null>(null);

  useEffect(() => {
    if (!attempt?.started_at || !durationMinutes) return;
    const deadline = new Date(attempt.started_at).getTime() + durationMinutes * 60_000;
    const tick = () => {
      const diff = Math.floor((deadline - Date.now()) / 1000);
      setSecsLeft(Math.max(0, diff));
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [attempt?.started_at, durationMinutes]);

  return secsLeft;
}

function CountdownTimer({ secsLeft }: { secsLeft: number }) {
  const mins = Math.floor(secsLeft / 60);
  const secs = secsLeft % 60;
  const urgent = secsLeft <= 60;
  return (
    <div
      className={`flex items-center gap-1.5 text-sm font-mono font-semibold px-3 py-1 rounded-full border ${
        urgent
          ? "bg-rose-50 border-rose-300 text-rose-700 animate-pulse"
          : "bg-slate-50 border-slate-200 text-slate-700"
      }`}
    >
      ⏱ {mins}:{String(secs).padStart(2, "0")}
    </div>
  );
}

export function TakeQuizPage() {
  const { quizId } = useParams<{ quizId: string }>();
  const navigate = useNavigate();
  const [attempt, setAttempt] = useState<AttemptRead | null>(null);
  const startedRef = useRef(false);

  // Check for an existing IN_PROGRESS attempt for this quiz BEFORE calling
  // POST. The POST is idempotent (backend returns the existing one if found),
  // but we need to know up-front so we can: (a) show "Resuming" vs "Starting"
  // in the loading state, and (b) only call POST once the check is done.
  const { data: inProgressData, isSuccess: progressChecked } = useQuery({
    queryKey: ["my-attempts", "IN_PROGRESS"],
    queryFn: () =>
      api<PaginatedAttempts>("/attempts?status=IN_PROGRESS&page_size=100"),
    enabled: !!quizId,
    staleTime: 0,
  });

  const isResuming =
    inProgressData?.items.some((a) => a.quiz_id === quizId) ?? false;

  useEffect(() => {
    if (!quizId || !progressChecked || startedRef.current) return;
    startedRef.current = true;
    api<AttemptRead>(`/quizzes/${quizId}/attempts`, { method: "POST" })
      .then(setAttempt)
      .catch((err) => {
        alert(err.message ?? "Failed to start quiz");
        navigate("/student");
      });
  }, [quizId, progressChecked, navigate]);

  const { data: quiz } = useQuery({
    queryKey: ["quiz", quizId],
    queryFn: () => api<QuizSummary>(`/quizzes/${quizId}`),
    enabled: !!quizId,
  });

  const secsLeft = useCountdown(attempt, quiz?.duration_minutes);

  if (!attempt || !quiz)
    return (
      <p className="text-slate-500">
        {progressChecked && isResuming ? "Resuming your attempt…" : "Loading attempt…"}
      </p>
    );

  return (
    <>
      {/* Timer bar */}
      <div className="flex items-center justify-between mb-4">
        <span className="text-sm text-slate-500">{quiz.title}</span>
        {secsLeft !== null && <CountdownTimer secsLeft={secsLeft} />}
      </div>

      {isResuming && (
        <div className="mb-4 px-4 py-2.5 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800">
          You already have an attempt in progress for this quiz — resuming where you left off.
        </div>
      )}
      {quiz.is_adaptive ? (
        <AdaptiveQuiz attempt={attempt} secsLeft={secsLeft} />
      ) : (
        <LinearQuiz attempt={attempt} secsLeft={secsLeft} />
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Adaptive flow: one question at a time, backend picks next based on ability.
// No Prev/Next, no jump-to grid. Student can submit early with a warning.
// ---------------------------------------------------------------------------

function AdaptiveQuiz({ attempt, secsLeft }: { attempt: AttemptRead; secsLeft: number | null }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [selectedOptionId, setSelectedOptionId] = useState<string | null>(null);
  const [textAnswer, setTextAnswer] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [lastResult, setLastResult] = useState<{
    isCorrect: boolean | null;
  } | null>(null);
  const [locked, setLocked] = useState(false);
  const totalRef = useRef<number | null>(null);

  const { data: nq, refetch } = useQuery({
    queryKey: ["next-question", attempt.id],
    queryFn: () =>
      api<NextQuestionResponse>(`/attempts/${attempt.id}/next-question`),
  });

  useEffect(() => {
    if (nq && totalRef.current === null) totalRef.current = nq.remaining;
  }, [nq]);

  const submit = useMutation({
    mutationFn: async () => {
      if (!nq?.question) return null;
      return api<{ id: string; is_correct: boolean | null }>(
        `/attempts/${attempt.id}/answers`,
        {
          method: "POST",
          json: {
            question_id: nq.question.id,
            selected_option_id: selectedOptionId,
            text_answer: textAnswer || null,
          },
        },
      );
    },
    onSuccess: (result) => {
      if (!result) return;
      setLastResult({ isCorrect: result.is_correct });
      setLocked(true);
      setTimeout(() => {
        setLastResult(null);
        setLocked(false);
        setSelectedOptionId(null);
        setTextAnswer("");
        refetch();
      }, FEEDBACK_MS);
    },
  });

  const complete = useMutation({
    mutationFn: () =>
      api<AttemptRead>(`/attempts/${attempt.id}/complete`, { method: "POST" }),
    onSuccess: (a) => {
      queryClient.invalidateQueries({ queryKey: ["student-dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["my-attempts"] });
      navigate(`/student/attempts/${a.id}/results`);
    },
  });

  // When timer hits 0 the backend will abandon the attempt on the next request.
  // Redirect to attempts list so the student sees the ABANDONED status.
  useEffect(() => {
    if (secsLeft === 0) navigate("/student/attempts");
  }, [secsLeft, navigate]);

  if (!nq) return <p className="text-slate-500">Loading…</p>;

  if (secsLeft === 0)
    return (
      <div className="bg-rose-50 border border-rose-200 rounded-xl px-5 py-6 text-center space-y-2">
        <p className="text-lg font-semibold text-rose-700">Time's up!</p>
        <p className="text-sm text-rose-600">Your attempt has been automatically abandoned. Redirecting…</p>
      </div>
    );

  const total = totalRef.current ?? nq.remaining;
  const answered = Math.max(0, total - nq.remaining);
  const progressPct = total > 0 ? (answered / total) * 100 : 0;

  // No more questions — show "submit quiz" screen.
  if (nq.question === null) {
    return (
      <div className="bg-white rounded-2xl ring-1 ring-slate-200 p-6 max-w-2xl mx-auto">
        <h2 className="text-lg font-semibold mb-1">All questions answered</h2>
        <p className="text-sm text-slate-500 mb-4">
          Submit to see your score and any AI feedback. You won't be able to
          change answers afterwards.
        </p>
        <button
          onClick={() => complete.mutate()}
          disabled={complete.isPending}
          className="bg-indigo-600 text-white rounded-lg px-4 py-2 font-medium hover:bg-indigo-700 disabled:bg-indigo-300 disabled:cursor-not-allowed transition-colors"
        >
          {complete.isPending ? "Submitting…" : "Submit quiz"}
        </button>
      </div>
    );
  }

  const q = nq.question;
  const isMcq = q.type === "MULTIPLE_CHOICE" || q.type === "TRUE_FALSE";
  const canSubmit =
    !submit.isPending &&
    !locked &&
    (isMcq ? !!selectedOptionId : textAnswer.trim().length > 0);

  return (
    <div className="space-y-4">
      {/* Prominent banner so the student knows the rules of the adaptive flow. */}
      <div className="bg-indigo-50 border border-indigo-200 text-indigo-900 rounded-xl px-4 py-3 flex items-start gap-3">
        <SparkIcon />
        <div className="text-sm leading-relaxed">
          <span className="font-semibold">Adaptive quiz.</span>{" "}
          The next question's difficulty is chosen automatically based on
          your running performance.{" "}
          <span className="font-semibold">
            Once you submit an answer you can't go back to it
          </span>{" "}
          — you'll move forward to a new question.
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_280px] items-start">
        <div className="space-y-4 order-2 lg:order-1 min-w-0">
          <QuestionCard
            q={q}
            selectedOptionId={selectedOptionId}
            onPickOption={setSelectedOptionId}
            textValue={textAnswer}
            onTextChange={setTextAnswer}
            locked={locked}
            banner={
              lastResult && <FeedbackBanner isCorrect={lastResult.isCorrect} />
            }
          />

          <div className="flex justify-end">
            <button
              onClick={() => submit.mutate()}
              disabled={!canSubmit}
              className="bg-indigo-600 text-white rounded-lg px-5 py-2.5 font-medium hover:bg-indigo-700 disabled:bg-indigo-300 disabled:cursor-not-allowed transition-colors"
            >
              {submit.isPending ? "Submitting…" : "Submit answer"}
            </button>
          </div>
        </div>

        <aside className="order-1 lg:order-2 lg:sticky lg:top-20 space-y-4">
          <div className="bg-white rounded-2xl ring-1 ring-slate-200 p-5 space-y-4">
            <ProgressMeta
              currentNumber={answered + 1}
              total={total}
              answered={answered}
              progressPct={progressPct}
            />
          </div>

          <button
            onClick={() => setConfirmOpen(true)}
            disabled={answered === 0}
            className="w-full bg-indigo-600 text-white rounded-lg px-4 py-2.5 font-medium hover:bg-indigo-700 disabled:bg-indigo-300 disabled:cursor-not-allowed transition-colors"
            title={answered === 0 ? "Answer at least one question first" : ""}
          >
            Submit quiz early
          </button>
        </aside>
      </div>

      <ConfirmModal
        open={confirmOpen}
        title={`Submit with ${total - answered} unanswered?`}
        message={`You haven't answered ${total - answered} of ${total} question${
          total - answered === 1 ? "" : "s"
        }. Unanswered questions count as wrong. Continue?`}
        confirmLabel={complete.isPending ? "Submitting…" : "Yes, submit"}
        confirmDisabled={complete.isPending}
        confirmDanger
        onConfirm={() => {
          setConfirmOpen(false);
          complete.mutate();
        }}
        onCancel={() => setConfirmOpen(false)}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Linear flow (non-adaptive quizzes): all snapshot questions loaded up-front,
// student navigates freely with Prev/Next, can re-answer until submit.
// ---------------------------------------------------------------------------

function LinearQuiz({ attempt, secsLeft }: { attempt: AttemptRead; secsLeft: number | null }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [items, setItems] = useState<AttemptQuestionItem[] | null>(null);
  const [idx, setIdx] = useState(0);
  const [textDraft, setTextDraft] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [savedHint, setSavedHint] = useState<{ qid: string; ts: number } | null>(
    null,
  );

  useEffect(() => {
    api<AttemptQuestionItem[]>(`/attempts/${attempt.id}/questions`)
      .then((data) => {
        setItems(data);
        const firstUnanswered = data.findIndex(
          (it) => it.selected_option_id === null && !it.text_answer,
        );
        setIdx(firstUnanswered === -1 ? 0 : firstUnanswered);
      })
      .catch(() => setItems([]));
  }, [attempt]);

  useEffect(() => {
    if (!items || !items[idx]) return;
    setTextDraft(items[idx].text_answer ?? "");
  }, [idx, items]);

  const save = useMutation({
    mutationFn: async (vars: {
      questionId: string;
      selectedOptionId: string | null;
      textAnswer: string | null;
    }) => {
      return api<{ id: string; is_correct: boolean | null }>(
        `/attempts/${attempt.id}/answers`,
        {
          method: "POST",
          json: {
            question_id: vars.questionId,
            selected_option_id: vars.selectedOptionId,
            text_answer: vars.textAnswer,
          },
        },
      );
    },
    onSuccess: (result, vars) => {
      setItems((prev) =>
        prev
          ? prev.map((it) =>
              it.question.id === vars.questionId
                ? {
                    ...it,
                    selected_option_id: vars.selectedOptionId,
                    text_answer: vars.textAnswer,
                    is_correct: result.is_correct,
                  }
                : it,
            )
          : prev,
      );
      setSavedHint({ qid: vars.questionId, ts: Date.now() });
    },
  });

  const complete = useMutation({
    mutationFn: () =>
      api<AttemptRead>(`/attempts/${attempt.id}/complete`, { method: "POST" }),
    onSuccess: (a) => {
      queryClient.invalidateQueries({ queryKey: ["student-dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["my-attempts"] });
      navigate(`/student/attempts/${a.id}/results`);
    },
  });

  useEffect(() => {
    if (secsLeft === 0) navigate("/student/attempts");
  }, [secsLeft, navigate]);

  if (!items) return <p className="text-slate-500">Loading…</p>;
  if (items.length === 0)
    return <p className="text-slate-500">This quiz has no active questions.</p>;

  if (secsLeft === 0)
    return (
      <div className="bg-rose-50 border border-rose-200 rounded-xl px-5 py-6 text-center space-y-2">
        <p className="text-lg font-semibold text-rose-700">Time's up!</p>
        <p className="text-sm text-rose-600">Your attempt has been automatically abandoned. Redirecting…</p>
      </div>
    );

  const item = items[idx];
  const q = item.question;
  const isMcq = q.type === "MULTIPLE_CHOICE" || q.type === "TRUE_FALSE";
  const total = items.length;
  const answeredCount = items.filter(
    (it) => it.selected_option_id !== null || (it.text_answer ?? "").trim().length > 0,
  ).length;

  const pickOption = (optionId: string) => {
    setItems((prev) =>
      prev
        ? prev.map((it, i) =>
            i === idx ? { ...it, selected_option_id: optionId } : it,
          )
        : prev,
    );
    save.mutate({
      questionId: q.id,
      selectedOptionId: optionId,
      textAnswer: null,
    });
  };

  const saveText = () => {
    const cleaned = textDraft.trim();
    if (cleaned === (item.text_answer ?? "")) return;
    save.mutate({
      questionId: q.id,
      selectedOptionId: null,
      textAnswer: cleaned || null,
    });
  };

  const goPrev = () => {
    if (!isMcq) saveText();
    setIdx((i) => Math.max(0, i - 1));
  };
  const goNext = () => {
    if (!isMcq) saveText();
    setIdx((i) => Math.min(total - 1, i + 1));
  };

  const showSavedHint =
    savedHint && savedHint.qid === q.id && Date.now() - savedHint.ts < 1500;

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_280px] items-start">
      <div className="space-y-4 order-2 lg:order-1 min-w-0">
        <QuestionCard
          q={q}
          selectedOptionId={item.selected_option_id}
          onPickOption={pickOption}
          textValue={textDraft}
          onTextChange={setTextDraft}
          onTextBlur={saveText}
          banner={
            showSavedHint ? (
              <p className="mt-3 text-xs text-emerald-600 flex items-center gap-1">
                <CheckIcon size={14} /> Saved
              </p>
            ) : undefined
          }
        />

        <div className="flex items-center justify-between gap-2">
          <button
            onClick={goPrev}
            disabled={idx === 0}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-slate-700 hover:text-slate-900 hover:bg-slate-100 disabled:text-slate-300 disabled:hover:bg-transparent disabled:cursor-not-allowed transition-colors"
          >
            <ArrowLeftIcon /> Previous
          </button>
          <button
            onClick={goNext}
            disabled={idx === total - 1}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-slate-700 hover:text-slate-900 hover:bg-slate-100 disabled:text-slate-300 disabled:hover:bg-transparent disabled:cursor-not-allowed transition-colors"
          >
            Next <ArrowRightIcon />
          </button>
        </div>
      </div>

      <aside className="order-1 lg:order-2 lg:sticky lg:top-20 space-y-4">
        <div className="bg-white rounded-2xl ring-1 ring-slate-200 p-5 space-y-4">
          <ProgressMeta
            currentNumber={idx + 1}
            total={total}
            answered={answeredCount}
            progressPct={(answeredCount / total) * 100}
          />

          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">
              Questions
            </p>
            <div className="flex flex-wrap gap-1.5">
              {items.map((it, i) => {
                const answered =
                  it.selected_option_id !== null ||
                  (it.text_answer ?? "").trim().length > 0;
                const isCurrent = i === idx;
                return (
                  <button
                    key={it.question.id}
                    onClick={() => {
                      if (!isMcq) saveText();
                      setIdx(i);
                    }}
                    aria-label={`Jump to question ${i + 1}${answered ? " (answered)" : ""}`}
                    className={`w-8 h-8 rounded-md text-xs font-semibold transition-colors ${
                      isCurrent
                        ? "bg-indigo-600 text-white ring-2 ring-indigo-200"
                        : answered
                          ? "bg-emerald-100 text-emerald-800 hover:bg-emerald-200"
                          : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                    }`}
                  >
                    {i + 1}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="pt-1 flex flex-wrap items-center gap-3 text-[11px] text-slate-500">
            <span className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded-sm bg-emerald-200 ring-1 ring-emerald-300" />
              Answered
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded-sm bg-slate-200 ring-1 ring-slate-300" />
              Pending
            </span>
          </div>
        </div>

        <button
          onClick={() => setConfirmOpen(true)}
          className="w-full bg-indigo-600 text-white rounded-lg px-4 py-2.5 font-medium hover:bg-indigo-700 transition-colors"
        >
          Submit quiz
        </button>
      </aside>

      <ConfirmModal
        open={confirmOpen}
        title={
          answeredCount === total
            ? "Submit your quiz?"
            : `Submit with ${total - answeredCount} unanswered?`
        }
        message={
          answeredCount === total
            ? "Once submitted, you'll see your score and any AI feedback. You won't be able to change answers."
            : `You haven't answered ${total - answeredCount} of ${total} question${
                total - answeredCount === 1 ? "" : "s"
              }. Unanswered questions count as wrong. Continue?`
        }
        confirmLabel={complete.isPending ? "Submitting…" : "Yes, submit"}
        confirmDisabled={complete.isPending}
        confirmDanger={answeredCount !== total}
        onConfirm={() => {
          if (!isMcq) saveText();
          setConfirmOpen(false);
          complete.mutate();
        }}
        onCancel={() => setConfirmOpen(false)}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shared visual components
// ---------------------------------------------------------------------------

interface QuestionCardProps {
  q: QuestionStudentRead;
  selectedOptionId: string | null;
  onPickOption: (optionId: string) => void;
  textValue: string;
  onTextChange: (v: string) => void;
  onTextBlur?: () => void;
  locked?: boolean;
  banner?: React.ReactNode;
}

function QuestionCard({
  q,
  selectedOptionId,
  onPickOption,
  textValue,
  onTextChange,
  onTextBlur,
  locked,
  banner,
}: QuestionCardProps) {
  const isMcq = q.type === "MULTIPLE_CHOICE" || q.type === "TRUE_FALSE";

  return (
    <div className="bg-white rounded-2xl ring-1 ring-slate-200 p-6 sm:p-8">
      <div className="flex items-start justify-between gap-3 mb-5">
        <p className="text-lg sm:text-xl text-slate-900 leading-snug">
          {q.text}
        </p>
        <DifficultyBadge difficulty={q.difficulty} />
      </div>

      {isMcq ? (
        <ul className="space-y-2.5">
          {q.options.map((o, i) => {
            const selected = selectedOptionId === o.id;
            return (
              <li key={o.id}>
                <button
                  type="button"
                  onClick={() => onPickOption(o.id)}
                  disabled={locked}
                  className={`group w-full flex items-center gap-3 border-2 rounded-xl px-4 py-3 text-left transition-all ${
                    selected
                      ? "border-indigo-500 bg-indigo-50/60 shadow-sm"
                      : "border-slate-200 hover:border-indigo-300 hover:bg-slate-50"
                  } ${locked ? "pointer-events-none opacity-70" : ""}`}
                >
                  <span
                    aria-hidden="true"
                    className={`shrink-0 w-7 h-7 rounded-full grid place-items-center text-xs font-semibold transition-colors ${
                      selected
                        ? "bg-indigo-600 text-white"
                        : "bg-slate-100 text-slate-600 group-hover:bg-slate-200"
                    }`}
                  >
                    {OPTION_LETTERS[i] ?? "•"}
                  </span>
                  <span
                    className={`flex-1 text-sm sm:text-base ${
                      selected ? "text-slate-900 font-medium" : "text-slate-700"
                    }`}
                  >
                    {o.text}
                  </span>
                  {selected && (
                    <CheckIcon className="text-indigo-600 shrink-0" />
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      ) : (
        <textarea
          className={`w-full border-2 border-slate-200 rounded-xl px-3 py-2.5 text-slate-900 placeholder:text-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100 transition-colors ${
            locked ? "pointer-events-none opacity-70" : ""
          }`}
          rows={4}
          value={textValue}
          onChange={(e) => onTextChange(e.target.value)}
          onBlur={onTextBlur}
          placeholder="Type your answer…"
          disabled={locked}
        />
      )}

      {banner}
    </div>
  );
}

function ProgressMeta({
  currentNumber,
  total,
  answered,
  progressPct,
}: {
  currentNumber: number;
  total: number;
  answered: number;
  progressPct: number;
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between text-sm text-slate-500 mb-1.5">
        <span>
          Question{" "}
          <span className="font-semibold text-slate-700">{currentNumber}</span>{" "}
          of <span className="font-semibold text-slate-700">{total}</span>
        </span>
        <span className="text-xs">
          {answered}/{total}
        </span>
      </div>
      <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <div
          className="h-full bg-indigo-500 transition-[width] duration-500"
          style={{ width: `${progressPct}%` }}
        />
      </div>
    </div>
  );
}

function DifficultyBadge({ difficulty }: { difficulty: Difficulty }) {
  const styles: Record<Difficulty, string> = {
    EASY: "bg-emerald-50 text-emerald-700 ring-emerald-200",
    MEDIUM: "bg-amber-50 text-amber-700 ring-amber-200",
    HARD: "bg-rose-50 text-rose-700 ring-rose-200",
  };
  return (
    <span
      className={`text-xs font-medium px-2 py-0.5 rounded-full ring-1 shrink-0 ${styles[difficulty]}`}
    >
      {difficulty}
    </span>
  );
}

function FeedbackBanner({ isCorrect }: { isCorrect: boolean | null }) {
  const correct = isCorrect === true;
  const wrong = isCorrect === false;
  return (
    <div
      role="status"
      className={`mt-4 flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium ${
        correct
          ? "bg-emerald-50 text-emerald-800 ring-1 ring-emerald-200"
          : wrong
            ? "bg-amber-50 text-amber-900 ring-1 ring-amber-200"
            : "bg-slate-50 text-slate-700 ring-1 ring-slate-200"
      }`}
    >
      {correct ? (
        <CheckIcon size={16} className="text-emerald-600" />
      ) : (
        <ArrowRightIcon />
      )}
      <span>
        {correct
          ? "Correct! Difficulty will adjust."
          : wrong
            ? "Not quite — moving to an easier one."
            : "Recorded."}
      </span>
    </div>
  );
}

function CheckIcon({
  className = "",
  size = 18,
}: {
  className?: string;
  size?: number;
}) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

function ArrowLeftIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <line x1="19" y1="12" x2="5" y2="12" />
      <polyline points="12 19 5 12 12 5" />
    </svg>
  );
}

function SparkIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="shrink-0 mt-0.5 text-indigo-600"
      aria-hidden="true"
    >
      <path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1" />
    </svg>
  );
}

function ArrowRightIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <line x1="5" y1="12" x2="19" y2="12" />
      <polyline points="12 5 19 12 12 19" />
    </svg>
  );
}
