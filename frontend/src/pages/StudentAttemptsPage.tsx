import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { api } from "../api";
import type { AttemptStatus, PaginatedAttempts } from "../api";

type StatusFilter = "ALL" | AttemptStatus;

const TABS: { key: StatusFilter; label: string }[] = [
  { key: "ALL", label: "All" },
  { key: "IN_PROGRESS", label: "In progress" },
  { key: "COMPLETED", label: "Completed" },
  { key: "ABANDONED", label: "Abandoned" },
];

const PAGE_SIZE = 10;

export function StudentAttemptsPage() {
  const [params, setParams] = useSearchParams();

  const status = (params.get("status") as StatusFilter) ?? "ALL";
  const search = params.get("q") ?? "";
  const page = Number(params.get("page") ?? 1);

  // Local search input that we debounce into the URL.
  const [searchDraft, setSearchDraft] = useState(search);
  useEffect(() => {
    const handle = setTimeout(() => {
      const next = new URLSearchParams(params);
      if (searchDraft) {
        next.set("q", searchDraft);
      } else {
        next.delete("q");
      }
      next.set("page", "1");
      setParams(next, { replace: true });
    }, 300);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchDraft]);

  const queryString = (() => {
    const sp = new URLSearchParams();
    if (status !== "ALL") sp.set("status", status);
    if (search) sp.set("search", search);
    sp.set("page", String(page));
    sp.set("page_size", String(PAGE_SIZE));
    return sp.toString();
  })();

  const { data, isLoading } = useQuery({
    queryKey: ["my-attempts", status, search, page],
    queryFn: () => api<PaginatedAttempts>(`/attempts?${queryString}`),
  });

  const setStatus = (next: StatusFilter) => {
    const sp = new URLSearchParams(params);
    if (next === "ALL") sp.delete("status");
    else sp.set("status", next);
    sp.set("page", "1");
    setParams(sp);
  };

  const setPage = (next: number) => {
    const sp = new URLSearchParams(params);
    sp.set("page", String(next));
    setParams(sp);
  };

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-900">My attempts</h2>
        <Link
          to="/student"
          className="text-sm text-slate-600 hover:text-slate-900"
        >
          ← Dashboard
        </Link>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-1.5 border-b border-slate-200">
        {TABS.map((t) => {
          const active = status === t.key;
          return (
            <button
              key={t.key}
              onClick={() => setStatus(t.key)}
              className={`px-3 py-2 text-sm font-medium -mb-px border-b-2 transition-colors ${
                active
                  ? "text-indigo-700 border-indigo-600"
                  : "text-slate-600 border-transparent hover:text-slate-900"
              }`}
            >
              {t.label}
            </button>
          );
        })}
      </div>

      {/* Search */}
      <div className="relative">
        <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <input
          type="search"
          placeholder="Search by quiz title…"
          className="w-full sm:max-w-sm rounded-lg border border-slate-300 pl-9 pr-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
          value={searchDraft}
          onChange={(e) => setSearchDraft(e.target.value)}
        />
      </div>

      {/* List */}
      {isLoading ? (
        <p className="text-sm text-slate-500">Loading…</p>
      ) : !data || data.items.length === 0 ? (
        <p className="text-sm text-slate-500 py-8 text-center">
          {search
            ? `No attempts matching "${search}".`
            : status === "ALL"
              ? "You haven't started any quizzes yet."
              : `No ${TABS.find((t) => t.key === status)?.label.toLowerCase()} attempts.`}
        </p>
      ) : (
        <ul className="space-y-2">
          {data.items.map((a) => (
            <li
              key={a.id}
              className="bg-white rounded-lg ring-1 ring-slate-200 p-4 flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3"
            >
              <div className="flex-1 min-w-0">
                <h3 className="font-medium text-slate-900">{a.quiz_title}</h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  {a.quiz_subject} · by {a.quiz_author} · started{" "}
                  {formatDate(a.started_at)}
                  {a.completed_at && ` · finished ${formatDate(a.completed_at)}`}
                </p>
              </div>
              <div className="flex items-center gap-3 sm:shrink-0">
                <StatusPill status={a.status} score={a.score} />
                {a.status === "IN_PROGRESS" ? (
                  <Link
                    to={`/student/quizzes/${a.quiz_id}/take`}
                    className="text-sm bg-indigo-600 text-white rounded-lg px-3 py-1.5 hover:bg-indigo-700 ml-auto sm:ml-0"
                  >
                    Resume →
                  </Link>
                ) : a.status === "COMPLETED" ? (
                  <Link
                    to={`/student/attempts/${a.id}/results`}
                    className="text-sm text-indigo-700 hover:text-indigo-900 underline ml-auto sm:ml-0"
                  >
                    Results
                  </Link>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      )}

      {/* Pagination */}
      {data && data.total > PAGE_SIZE && (
        <div className="flex items-center justify-between text-sm pt-2">
          <span className="text-slate-500">
            Page {page} of {totalPages} · {data.total} total
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(page - 1)}
              disabled={page <= 1}
              className="px-3 py-1.5 rounded-lg border border-slate-300 text-slate-700 disabled:text-slate-300 disabled:cursor-not-allowed hover:bg-slate-50"
            >
              Previous
            </button>
            <button
              onClick={() => setPage(page + 1)}
              disabled={!data.has_next}
              className="px-3 py-1.5 rounded-lg border border-slate-300 text-slate-700 disabled:text-slate-300 disabled:cursor-not-allowed hover:bg-slate-50"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function StatusPill({
  status,
  score,
}: {
  status: AttemptStatus;
  score: number | null;
}) {
  if (status === "IN_PROGRESS") {
    return (
      <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 ring-1 ring-amber-200">
        In progress
      </span>
    );
  }
  if (status === "COMPLETED") {
    return (
      <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200">
        {score === null ? "Completed" : `${score.toFixed(0)}%`}
      </span>
    );
  }
  return (
    <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 ring-1 ring-slate-200">
      Abandoned
    </span>
  );
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function SearchIcon({ className = "" }: { className?: string }) {
  return (
    <svg
      className={className}
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.3-4.3" />
    </svg>
  );
}
