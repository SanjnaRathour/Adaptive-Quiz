import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { api } from "../api";
import type { QuizSummary, TeacherOverview } from "../api";

export function TeacherDashboardPage() {
  const { data: overview } = useQuery({
    queryKey: ["teacher-overview"],
    queryFn: () => api<TeacherOverview>("/analytics/overview"),
  });
  const { data: quizzes } = useQuery({
    queryKey: ["quizzes"],
    queryFn: () => api<QuizSummary[]>("/quizzes"),
  });

  return (
    <div className="space-y-6">
      <section>
        <h2 className="text-lg font-semibold mb-2">Overview</h2>
        {overview ? (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <Stat label="Quizzes authored" value={overview.quizzes_authored} />
            <Stat label="Published" value={overview.quizzes_published} />
            <Stat
              label="Student attempts"
              value={overview.total_student_attempts}
            />
            <Stat
              label="Avg score"
              value={
                overview.average_score_across_quizzes === null
                  ? "—"
                  : `${overview.average_score_across_quizzes.toFixed(1)}%`
              }
            />
          </div>
        ) : (
          <Skeleton />
        )}
      </section>

      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold">Your quizzes</h2>
          <Link
            to="/teacher/quizzes/new"
            className="text-sm bg-indigo-600 text-white rounded-lg px-3 py-1.5 hover:bg-indigo-700"
          >
            + New quiz
          </Link>
        </div>
        {quizzes ? (
          quizzes.length === 0 ? (
            <p className="text-sm text-slate-500">
              You haven&apos;t authored any quizzes yet —{" "}
              <Link to="/teacher/quizzes/new" className="underline">
                create your first one
              </Link>
              .
            </p>
          ) : (
            <ul className="grid sm:grid-cols-2 gap-3">
              {quizzes.map((q) => (
                <li
                  key={q.id}
                  className="bg-white rounded-lg border border-slate-200 p-4"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <h3 className="font-medium text-slate-900 break-words">
                        {q.title}
                      </h3>
                      <p className="text-sm text-slate-500">
                        {q.subject} · {q.question_count} question
                        {q.question_count === 1 ? "" : "s"}
                      </p>
                    </div>
                    <span
                      className={`text-xs px-2 py-0.5 rounded ${
                        q.is_published
                          ? "bg-emerald-100 text-emerald-700"
                          : "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {q.is_published ? "Published" : "Draft"}
                    </span>
                  </div>
                  <div className="mt-3 flex gap-3 text-sm">
                    <Link
                      to={`/teacher/quizzes/${q.id}`}
                      className="text-slate-700 hover:text-slate-900 underline"
                    >
                      Manage
                    </Link>
                    <Link
                      to={`/teacher/quizzes/${q.id}/analytics`}
                      className="text-slate-700 hover:text-slate-900 underline"
                    >
                      Analytics
                    </Link>
                  </div>
                </li>
              ))}
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

function Skeleton() {
  return <div className="animate-pulse h-20 bg-slate-100 rounded-lg" />;
}
