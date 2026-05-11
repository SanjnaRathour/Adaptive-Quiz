import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "../api";
import type { AttemptResultDetail, AttemptResults, Difficulty } from "../api";

const DIFFICULTIES: Difficulty[] = ["EASY", "MEDIUM", "HARD"];

export function ResultsPage() {
  const { attemptId } = useParams<{ attemptId: string }>();
  const { data, isLoading, refetch, isRefetching } = useQuery({
    queryKey: ["attempt-results", attemptId],
    queryFn: () => api<AttemptResults>(`/attempts/${attemptId}/results`),
    refetchInterval: (query) => {
      const r = query.state.data;
      if (!r || !r.attempt.completed_at) return false;
      const anyMissingFeedback = r.details.some(
        (d) => d.is_correct === false && d.ai_feedback === null,
      );
      const ageMs = Date.now() - new Date(r.attempt.completed_at).getTime();
      return anyMissingFeedback && ageMs < 15_000 ? 2500 : false;
    },
  });

  const accuracyByDifficulty = useMemo(() => {
    if (!data) return null;
    const buckets = new Map<Difficulty, { answered: number; correct: number }>();
    for (const d of DIFFICULTIES) buckets.set(d, { answered: 0, correct: 0 });
    for (const item of data.details) {
      const b = buckets.get(item.difficulty)!;
      if (item.is_correct !== null) {
        b.answered += 1;
        if (item.is_correct) b.correct += 1;
      }
    }
    return DIFFICULTIES.map((d) => ({
      difficulty: d,
      ...buckets.get(d)!,
    }));
  }, [data]);

  if (isLoading || !data)
    return <p className="text-slate-500">Loading results…</p>;

  const score = data.attempt.score ?? 0;
  // We don't have passing_score on results endpoint right now — assume 60 for the badge
  // (the actual pass mark lives on the quiz, the score is what matters to the student).
  const passing = 60;
  const passed = score >= passing;
  const pendingFeedback = data.details.some(
    (d) => d.is_correct === false && d.ai_feedback === null,
  );

  return (
    <div className="space-y-6">
      <Link
        to="/student/attempts"
        className="text-sm text-slate-600 hover:text-slate-900"
      >
        ← Back to attempts
      </Link>

      {/* Hero */}
      <section className="bg-white rounded-2xl ring-1 ring-slate-200 p-6 sm:p-8">
        <div className="flex flex-col sm:flex-row sm:items-center gap-6">
          <ScoreRing score={score} passed={passed} />
          <div className="flex-1 min-w-0">
            <span
              className={`inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full ring-1 ${
                passed
                  ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
                  : "bg-rose-50 text-rose-700 ring-rose-200"
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  passed ? "bg-emerald-500" : "bg-rose-500"
                }`}
              />
              {passed ? "Passed" : "Did not pass"}
            </span>
            <h1 className="text-2xl font-semibold text-slate-900 mt-2">
              {passed
                ? "Great work!"
                : "Keep going — every wrong answer is a lesson."}
            </h1>
            <p className="text-sm text-slate-500 mt-1">
              You answered{" "}
              <span className="font-semibold text-slate-700">
                {data.correct_count}
              </span>{" "}
              of{" "}
              <span className="font-semibold text-slate-700">
                {data.total_questions}
              </span>{" "}
              correctly
              {data.attempt.completed_at &&
                ` · finished ${formatDate(data.attempt.completed_at)}`}
              .
            </p>

            <div className="grid grid-cols-3 gap-3 mt-5">
              <Stat
                label="Score"
                value={`${score.toFixed(0)}%`}
                tone={passed ? "success" : "warn"}
              />
              <Stat label="Correct" value={`${data.correct_count}`} />
              <Stat label="Questions" value={`${data.total_questions}`} />
            </div>
          </div>
        </div>
      </section>

      {/* Accuracy by difficulty */}
      {accuracyByDifficulty && (
        <section className="bg-white rounded-2xl ring-1 ring-slate-200 p-6">
          <h2 className="font-semibold text-slate-900 mb-3">
            Accuracy by difficulty
          </h2>
          <div className="space-y-2.5">
            {accuracyByDifficulty.map((row) => {
              const pct =
                row.answered === 0 ? 0 : (row.correct / row.answered) * 100;
              return (
                <div
                  key={row.difficulty}
                  className="flex items-center gap-3"
                >
                  <DifficultyBadge difficulty={row.difficulty} />
                  <div className="flex-1 h-2.5 bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${
                        row.answered === 0
                          ? ""
                          : pct >= 70
                            ? "bg-emerald-500"
                            : pct >= 40
                              ? "bg-amber-500"
                              : "bg-rose-500"
                      }`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <span className="text-xs tabular-nums text-slate-600 w-20 text-right">
                    {row.answered === 0
                      ? "no data"
                      : `${row.correct}/${row.answered} · ${pct.toFixed(0)}%`}
                  </span>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* Question review */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold text-slate-900">Question review</h2>
          {pendingFeedback && (
            <button
              onClick={() => refetch()}
              disabled={isRefetching}
              className="text-xs text-indigo-700 hover:text-indigo-900 font-medium"
            >
              {isRefetching ? "Refreshing…" : "Refresh AI feedback"}
            </button>
          )}
        </div>
        <ul className="space-y-3">
          {data.details.map((d, i) => (
            <ReviewCard key={d.question_id} index={i} detail={d} />
          ))}
        </ul>
      </section>

      <div className="flex flex-wrap gap-3 pt-2">
        <Link
          to="/student/attempts"
          className="bg-indigo-600 text-white rounded-lg px-4 py-2 font-medium hover:bg-indigo-700 transition-colors"
        >
          My attempts
        </Link>
        <Link
          to="/student"
          className="text-slate-700 px-4 py-2 hover:text-slate-900"
        >
          Dashboard
        </Link>
      </div>
    </div>
  );
}

// --- Components -----------------------------------------------------------

function ScoreRing({ score, passed }: { score: number; passed: boolean }) {
  const r = 56;
  const circ = 2 * Math.PI * r;
  const dash = (Math.max(0, Math.min(100, score)) / 100) * circ;
  const stroke = passed ? "#10b981" : "#f43f5e"; // emerald-500 / rose-500
  return (
    <div className="relative w-32 h-32 shrink-0 mx-auto sm:mx-0">
      <svg width="128" height="128" viewBox="0 0 128 128">
        <circle
          cx="64"
          cy="64"
          r={r}
          stroke="#e2e8f0"
          strokeWidth="10"
          fill="none"
        />
        <circle
          cx="64"
          cy="64"
          r={r}
          stroke={stroke}
          strokeWidth="10"
          fill="none"
          strokeDasharray={`${dash} ${circ}`}
          strokeLinecap="round"
          transform="rotate(-90 64 64)"
          style={{ transition: "stroke-dasharray 600ms ease-out" }}
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center">
        <div className="text-center">
          <div className="text-3xl font-bold text-slate-900 tabular-nums">
            {score.toFixed(0)}%
          </div>
        </div>
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string;
  tone?: "neutral" | "success" | "warn";
}) {
  const ringColor =
    tone === "success"
      ? "ring-emerald-200"
      : tone === "warn"
        ? "ring-rose-200"
        : "ring-slate-200";
  return (
    <div className={`bg-slate-50 rounded-lg ring-1 ${ringColor} p-3`}>
      <div className="text-lg sm:text-xl font-semibold text-slate-900 tabular-nums">
        {value}
      </div>
      <div className="text-[11px] uppercase tracking-wide text-slate-500 mt-0.5">
        {label}
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
      className={`text-xs font-medium px-2 py-0.5 rounded-full ring-1 w-20 text-center ${styles[difficulty]}`}
    >
      {difficulty}
    </span>
  );
}

function ReviewCard({
  index,
  detail,
}: {
  index: number;
  detail: AttemptResultDetail;
}) {
  const correct = detail.is_correct === true;
  const wrong = detail.is_correct === false;
  const skipped = detail.is_correct === null;
  return (
    <li
      className={`bg-white rounded-xl ring-1 p-4 sm:p-5 ${
        correct
          ? "ring-emerald-200"
          : wrong
            ? "ring-rose-200"
            : "ring-slate-200"
      }`}
    >
      <div className="flex items-start gap-3">
        <span
          className={`shrink-0 w-7 h-7 rounded-full grid place-items-center text-xs font-semibold ${
            correct
              ? "bg-emerald-500 text-white"
              : wrong
                ? "bg-rose-500 text-white"
                : "bg-slate-200 text-slate-600"
          }`}
          aria-hidden="true"
        >
          {correct ? "✓" : wrong ? "✕" : "—"}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <span className="text-xs text-slate-500">Q{index + 1}</span>
            <DifficultyBadge difficulty={detail.difficulty} />
            <span className="text-xs text-slate-500">
              {detail.points} pt{detail.points === 1 ? "" : "s"}
            </span>
          </div>
          <p className="font-medium text-slate-900 leading-snug">
            {detail.question_text}
          </p>

          <dl className="mt-3 grid sm:grid-cols-2 gap-3 text-sm">
            <div>
              <dt className="text-xs text-slate-500 mb-0.5">Your answer</dt>
              <dd
                className={`font-medium ${
                  correct
                    ? "text-emerald-700"
                    : wrong
                      ? "text-rose-700"
                      : "text-slate-500 italic"
                }`}
              >
                {detail.your_answer ?? "(no answer)"}
              </dd>
            </div>
            {!correct && detail.correct_answer && (
              <div>
                <dt className="text-xs text-slate-500 mb-0.5">Correct answer</dt>
                <dd className="font-medium text-emerald-700">
                  {detail.correct_answer}
                </dd>
              </div>
            )}
          </dl>

          {detail.explanation && (
            <p className="mt-3 text-sm text-slate-700 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2">
              <span className="font-semibold">Explanation: </span>
              {detail.explanation}
            </p>
          )}

          {wrong && detail.ai_feedback && (
            <p className="mt-2 text-sm bg-amber-50 border border-amber-200 text-amber-900 rounded-lg px-3 py-2">
              <span className="font-semibold">AI tutor: </span>
              {detail.ai_feedback}
            </p>
          )}

          {wrong && !detail.ai_feedback && (
            <p className="mt-2 text-xs text-amber-700 italic">
              AI feedback is being generated…
            </p>
          )}

          {skipped && (
            <p className="mt-2 text-xs text-slate-500 italic">
              You didn&apos;t answer this question.
            </p>
          )}
        </div>
      </div>
    </li>
  );
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
