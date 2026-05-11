import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { api } from "../api";
import type { QuizAnalytics } from "../api";

export function TeacherQuizAnalyticsPage() {
  const { quizId } = useParams<{ quizId: string }>();
  const { data } = useQuery({
    queryKey: ["quiz-analytics", quizId],
    queryFn: () => api<QuizAnalytics>(`/analytics/quizzes/${quizId}`),
    enabled: !!quizId,
  });

  if (!data) return <p className="text-slate-500">Loading analytics…</p>;

  const maxBucket = Math.max(...data.score_distribution.map((b) => b.count), 1);

  return (
    <div className="space-y-6">
      <Link
        to={`/teacher/quizzes/${quizId}`}
        className="text-sm text-slate-600 hover:text-slate-900"
      >
        ← Back to quiz
      </Link>

      <header>
        <h2 className="text-xl font-semibold text-slate-900">{data.title}</h2>
        <p className="text-sm text-slate-500">Quiz analytics</p>
      </header>

      <section className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <Stat label="Total attempts" value={data.total_attempts} />
        <Stat label="Completed" value={data.completed_attempts} />
        <Stat
          label="Avg score"
          value={
            data.average_score === null
              ? "—"
              : `${data.average_score.toFixed(1)}%`
          }
        />
      </section>

      <section className="bg-white rounded-lg border border-slate-200 p-5">
        <h3 className="font-medium text-slate-700 mb-3">Score distribution</h3>
        <div className="space-y-2">
          {data.score_distribution.map((bucket) => (
            <div key={bucket.label} className="flex items-center gap-2">
              <span className="w-16 text-sm text-slate-600">
                {bucket.label}
              </span>
              <div className="flex-1 bg-slate-100 rounded h-3 overflow-hidden">
                <div
                  className="h-3 bg-slate-700"
                  style={{ width: `${(bucket.count / maxBucket) * 100}%` }}
                />
              </div>
              <span className="text-sm tabular-nums text-slate-600 w-10 text-right">
                {bucket.count}
              </span>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h3 className="font-medium text-slate-700 mb-3">Per-question accuracy</h3>
        {data.question_stats.length === 0 ? (
          <p className="text-sm text-slate-500">No questions yet.</p>
        ) : (
          <ul className="space-y-2">
            {data.question_stats.map((q, i) => (
              <li
                key={q.question_id}
                className="bg-white rounded-lg border border-slate-200 p-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1">
                    <p className="text-sm text-slate-500">
                      Q{i + 1} · {q.difficulty}
                    </p>
                    <p className="text-sm text-slate-900">{q.question_text}</p>
                  </div>
                  <span className="text-sm tabular-nums text-slate-700 whitespace-nowrap">
                    {q.times_correct}/{q.times_answered} ·{" "}
                    {q.times_answered === 0
                      ? "—"
                      : `${(q.accuracy * 100).toFixed(0)}%`}
                  </span>
                </div>
              </li>
            ))}
          </ul>
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
