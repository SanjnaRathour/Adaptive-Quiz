import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api } from "../api";
import type { NotificationRead, PaginatedNotifications } from "../api";
import { useAuth } from "../auth";

const PREVIEW_COUNT = 5;

export function NotificationBell() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const { data } = useQuery({
    queryKey: ["notifications", "preview"],
    queryFn: () =>
      api<PaginatedNotifications>(
        `/notifications?page=1&page_size=${PREVIEW_COUNT}`,
      ),
    refetchInterval: 30_000,
  });

  const items = data?.items ?? [];
  const unreadCount = data?.unread_count ?? 0;

  const markRead = useMutation({
    mutationFn: (id: string) =>
      api<NotificationRead>(`/notifications/${id}/read`, { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  // Close on outside click.
  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    };
    window.addEventListener("mousedown", onClick);
    return () => window.removeEventListener("mousedown", onClick);
  }, [open]);

  const handleClickItem = (n: NotificationRead) => {
    if (n.read_at === null) markRead.mutate(n.id);
    setOpen(false);
    if (n.related_quiz_id) {
      const path =
        user?.role === "STUDENT"
          ? `/student/quizzes/${n.related_quiz_id}/take`
          : `/teacher/quizzes/${n.related_quiz_id}`;
      navigate(path);
    }
  };

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="relative text-slate-600 hover:text-slate-900 p-1 rounded-lg hover:bg-slate-100"
        aria-label={`Notifications${unreadCount ? ` (${unreadCount} unread)` : ""}`}
        aria-expanded={open}
      >
        <BellIcon />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] px-1 bg-rose-500 text-white text-[10px] font-bold rounded-full grid place-items-center">
            {unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div
          role="menu"
          className="fixed left-2 right-2 top-14 z-30 sm:absolute sm:left-auto sm:right-0 sm:top-auto sm:mt-2 sm:w-80 bg-white rounded-xl shadow-lg ring-1 ring-slate-200 overflow-hidden"
        >
          <div className="px-4 py-3 border-b border-slate-200 flex items-center justify-between">
            <h3 className="font-semibold text-sm text-slate-900">
              Notifications
            </h3>
            {unreadCount > 0 && (
              <span className="text-xs text-slate-500">
                {unreadCount} unread
              </span>
            )}
          </div>

          <div className="max-h-80 overflow-y-auto">
            {data === undefined ? (
              <p className="px-4 py-6 text-sm text-slate-500">Loading…</p>
            ) : items.length === 0 ? (
              <p className="px-4 py-6 text-sm text-slate-500 text-center">
                You're all caught up.
              </p>
            ) : (
              <ul>
                {items.map((n) => (
                  <li key={n.id}>
                    <button
                      type="button"
                      onClick={() => handleClickItem(n)}
                      className={`w-full text-left px-4 py-3 hover:bg-slate-50 transition-colors border-b border-slate-100 last:border-b-0 ${
                        n.read_at === null ? "bg-indigo-50/30" : ""
                      }`}
                    >
                      <div className="flex items-start gap-2">
                        {n.read_at === null && (
                          <span
                            className="mt-1.5 w-2 h-2 rounded-full bg-indigo-500 shrink-0"
                            aria-label="Unread"
                          />
                        )}
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-slate-900">
                            {n.title}
                          </p>
                          <p className="text-xs text-slate-600 mt-0.5 line-clamp-2">
                            {n.message}
                          </p>
                          <p className="text-[11px] text-slate-400 mt-1">
                            {formatRelative(n.created_at)}
                          </p>
                        </div>
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {data && data.total > 0 && (
            <div className="px-4 py-2 border-t border-slate-200 bg-slate-50/50 text-center">
              <Link
                to="/notifications"
                onClick={() => setOpen(false)}
                className="text-sm font-medium text-indigo-700 hover:text-indigo-900"
              >
                View all ({data.total})
              </Link>
            </div>
          )}
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

function BellIcon() {
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
    >
      <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
      <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
    </svg>
  );
}
