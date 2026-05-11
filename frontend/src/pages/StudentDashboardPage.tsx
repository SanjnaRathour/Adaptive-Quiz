import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { Link } from "react-router-dom";

import { api } from "../api";
import type {
  PaginatedAttempts,
  QuizSummary,
  StudentDashboard,
} from "../api";

export function StudentDashboardPage() {
  const { data: stats } = useQuery({
    queryKey: ["student-dashboard"],
    queryFn: () => api<StudentDashboard>("/analytics/me"),
  });
  const { data: quizzes } = useQuery({
    queryKey: ["quizzes"],
    queryFn: () => api<QuizSummary[]>("/quizzes"),
  });

  // Which quizzes does the student already have an IN_PROGRESS attempt on?
  // We use this to relabel "Start" → "Resume" so they don't think a click
  // creates a fresh attempt (the backend is idempotent — it returns the
  // existing one — but the label should match reality).
  const { data: inProgress } = useQuery({
    queryKey: ["my-attempts", "IN_PROGRESS"],
    queryFn: () =>
      api<PaginatedAttempts>("/attempts?status=IN_PROGRESS&page_size=100"),
  });
  const inProgressByQuizId = useMemo(() => {
    const m = new Map<string, string>();
    for (const a of inProgress?.items ?? []) m.set(a.quiz_id, a.id);
    return m;
  }, [inProgress]);

  return (
    <div className="space-y-6">
      <section>
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-lg font-semibold">Your progress</h2>
          <Link
            to="/student/attempts"
            className="text-sm text-indigo-600 hover:text-indigo-700 font-medium"
          >
            View all attempts →
          </Link>
        </div>
        {stats ? (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <StatLink label="Attempts" value={stats.total_attempts} to="/student/attempts" />
            <StatLink
              label="Completed"
              value={stats.completed_attempts}
              to="/student/attempts?status=COMPLETED"
            />
            <StatLink
              label="In progress"
              value={stats.in_progress_attempts}
              to="/student/attempts?status=IN_PROGRESS"
              highlight={stats.in_progress_attempts > 0}
            />
            <Stat
              label="Avg score"
              value={
                stats.average_score === null
                  ? "—"
                  : `${stats.average_score.toFixed(1)}%`
              }
            />
          </div>
        ) : (
          <Skeleton />
        )}
        {stats && (
          <div className="mt-4 bg-white rounded-lg border border-slate-200 p-4">
            <h3 className="font-medium text-slate-700 mb-2">
              Accuracy by difficulty
            </h3>
            <div className="space-y-2">
              {stats.accuracy_by_difficulty.map((row) => (
                <div key={row.difficulty} className="flex items-center gap-2">
                  <span className="w-20 text-sm text-slate-600">
                    {row.difficulty}
                  </span>
                  <div className="flex-1 bg-slate-100 rounded h-2 overflow-hidden">
                    <div
                      className="h-2 bg-emerald-500"
                      style={{ width: `${row.accuracy * 100}%` }}
                    />
                  </div>
                  <span className="text-sm tabular-nums text-slate-600 w-16 text-right">
                    {row.answered === 0
                      ? "—"
                      : `${(row.accuracy * 100).toFixed(0)}%`}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>

      <section>
        <h2 className="text-lg font-semibold mb-2">Available quizzes</h2>
        {quizzes ? (
          quizzes.length === 0 ? (
            <p className="text-sm text-slate-500">
              No published quizzes yet — check back later.
            </p>
          ) : (
            <ul className="grid sm:grid-cols-2 gap-3">
              {quizzes.map((q) => {
                const resuming = inProgressByQuizId.has(q.id);
                return (
                  <li
                    key={q.id}
                    className={`bg-white rounded-lg border p-4 ${
                      resuming
                        ? "border-amber-300 bg-amber-50/30"
                        : "border-slate-200"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <h3 className="font-medium text-slate-900">{q.title}</h3>
                      {resuming && (
                        <span className="shrink-0 text-[11px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 ring-1 ring-amber-200">
                          In progress
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-slate-500 mt-0.5">
                      {q.subject} · {q.question_count} questions ·{" "}
                      {q.duration_minutes} min
                    </p>
                    <Link
                      to={`/student/quizzes/${q.id}/take`}
                      className={`mt-3 inline-block text-sm rounded-lg px-3 py-1.5 font-medium transition-colors ${
                        resuming
                          ? "bg-amber-600 text-white hover:bg-amber-700"
                          : "bg-indigo-600 text-white hover:bg-indigo-700"
                      }`}
                    >
                      {resuming ? "Resume →" : "Start →"}
                    </Link>
                  </li>
                );
              })}
            </ul>
          )
        ) : (
          <Skeleton />
        )}
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4">
      <div className="text-2xl font-semibold text-slate-900">{value}</div>
      <div className="text-xs text-slate-500 mt-1 uppercase tracking-wide">
        {label}
      </div>
    </div>
  );
}

function StatLink({
  label,
  value,
  to,
  highlight,
}: {
  label: string;
  value: number | string;
  to: string;
  highlight?: boolean;
}) {
  return (
    <Link
      to={to}
      className={`block bg-white rounded-lg border p-4 transition-colors hover:border-indigo-300 hover:bg-indigo-50/30 ${
        highlight ? "border-amber-300 bg-amber-50/40" : "border-slate-200"
      }`}
    >
      <div className="text-2xl font-semibold text-slate-900">{value}</div>
      <div className="text-xs text-slate-500 mt-1 uppercase tracking-wide">
        {label}
      </div>
    </Link>
  );
}

function Skeleton() {
  return <div className="animate-pulse h-20 bg-slate-100 rounded-lg" />;
}
