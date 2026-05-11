import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../auth";
import { Brand } from "./Brand";
import { NotificationBell } from "./NotificationBell";

export function AppShell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between gap-2">
          <Link to="/" aria-label="Home" className="min-w-0">
            <Brand />
          </Link>

          <div className="flex items-center gap-2 sm:gap-4">
            <NotificationBell />

            <div className="hidden md:flex items-center gap-2 text-sm">
              <span className="text-slate-700 font-medium truncate max-w-[10rem]">
                {user?.full_name}
              </span>
              <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 font-medium">
                {user?.role}
              </span>
            </div>

            <button
              onClick={logout}
              className="text-sm text-slate-600 hover:text-slate-900 font-medium"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-5xl w-full mx-auto px-4 py-6">
        {children}
      </main>
    </div>
  );
}
