import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";

import { api } from "../api";
import type { NotificationRead, PaginatedNotifications } from "../api";
import { useAuth } from "../auth";

type Filter = "ALL" | "UNREAD";
const TABS: { key: Filter; label: string }[] = [
  { key: "ALL", label: "All" },
  { key: "UNREAD", label: "Unread" },
];
const PAGE_SIZE = 15;

export function NotificationsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();

  const filter = (params.get("filter") as Filter) ?? "ALL";
  const page = Number(params.get("page") ?? 1);

  const queryString = (() => {
    const sp = new URLSearchParams();
    if (filter === "UNREAD") sp.set("unread_only", "true");
    sp.set("page", String(page));
    sp.set("page_size", String(PAGE_SIZE));
    return sp.toString();
  })();

  const { data, isLoading } = useQuery({
    queryKey: ["notifications", "all", filter, page],
    queryFn: () => api<PaginatedNotifications>(`/notifications?${queryString}`),
  });

  const markRead = useMutation({
    mutationFn: (id: string) =>
      api<NotificationRead>(`/notifications/${id}/read`, { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  const markAllRead = useMutation({
    mutationFn: () => api<number>("/notifications/read-all", { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  const setFilter = (next: Filter) => {
    const sp = new URLSearchParams(params);
    if (next === "ALL") sp.delete("filter");
    else sp.set("filter", next);
    sp.set("page", "1");
    setParams(sp);
  };
  const setPage = (next: number) => {
    const sp = new URLSearchParams(params);
    sp.set("page", String(next));
    setParams(sp);
  };

  const handleClick = (n: NotificationRead) => {
    if (n.read_at === null) markRead.mutate(n.id);
  };

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h2 className="text-lg font-semibold text-slate-900">Notifications</h2>
        <div className="flex items-center gap-3">
          <button
            onClick={() => markAllRead.mutate()}
            disabled={markAllRead.isPending || (data?.unread_count ?? 0) === 0}
            className="text-sm text-slate-700 hover:text-slate-900 disabled:text-slate-300 disabled:cursor-not-allowed font-medium"
          >
            {markAllRead.isPending ? "Marking…" : "Mark all read"}
          </button>
          <Link
            to={user?.role === "STUDENT" ? "/student" : "/teacher"}
            className="text-sm text-slate-600 hover:text-slate-900"
          >
            ← Back
          </Link>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1.5 border-b border-slate-200">
        {TABS.map((t) => {
          const active = filter === t.key;
          const count =
            t.key === "UNREAD"
              ? (data?.unread_count ?? 0)
              : (data?.total ?? 0);
          return (
            <button
              key={t.key}
              onClick={() => setFilter(t.key)}
              className={`px-3 py-2 text-sm font-medium -mb-px border-b-2 transition-colors ${
                active
                  ? "text-indigo-700 border-indigo-600"
                  : "text-slate-600 border-transparent hover:text-slate-900"
              }`}
            >
              {t.label}{" "}
              {count > 0 && (
                <span
                  className={`ml-1 text-xs px-1.5 py-0.5 rounded-full ${
                    active
                      ? "bg-indigo-100 text-indigo-700"
                      : "bg-slate-100 text-slate-600"
                  }`}
                >
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* List */}
      {isLoading ? (
        <p className="text-sm text-slate-500 py-6">Loading…</p>
      ) : !data || data.items.length === 0 ? (
        <p className="text-sm text-slate-500 py-12 text-center">
          {filter === "UNREAD"
            ? "No unread notifications. You're all caught up!"
            : "No notifications yet."}
        </p>
      ) : (
        <ul className="space-y-2">
          {data.items.map((n) => (
            <li
              key={n.id}
              className={`bg-white rounded-lg ring-1 transition-colors ${
                n.read_at === null
                  ? "ring-indigo-200 bg-indigo-50/40"
                  : "ring-slate-200"
              }`}
            >
              <button
                type="button"
                onClick={() => handleClick(n)}
                className="w-full text-left px-4 py-3 hover:bg-white/60"
              >
                <div className="flex items-start gap-3">
                  {n.read_at === null ? (
                    <span
                      className="mt-1.5 w-2 h-2 rounded-full bg-indigo-500 shrink-0"
                      aria-label="Unread"
                    />
                  ) : (
                    <span className="mt-1.5 w-2 h-2 shrink-0" />
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2 flex-wrap">
                      <h3 className="font-medium text-slate-900">{n.title}</h3>
                      <span className="text-xs text-slate-500">
                        {formatRelative(n.created_at)}
                      </span>
                    </div>
                    <p className="text-sm text-slate-700 mt-0.5">{n.message}</p>
                    <span className="inline-block mt-1.5 text-[11px] uppercase tracking-wide text-slate-500">
                      {n.type.replace(/_/g, " ").toLowerCase()}
                    </span>
                  </div>
                </div>
              </button>
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

function formatRelative(iso: string): string {
  const then = new Date(iso).getTime();
  const diff = Date.now() - then;
  const sec = Math.round(diff / 1000);
  if (sec < 60) return "just now";
  const min = Math.round(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.round(hr / 24);
  if (day < 7) return `${day}d ago`;
  return new Date(iso).toLocaleDateString();
}
