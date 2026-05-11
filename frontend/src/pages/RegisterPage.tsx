import { useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../auth";
import { Brand } from "../components/Brand";
import { PasswordInput } from "../components/PasswordInput";

export function RegisterPage() {
  const { register } = useAuth();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"STUDENT" | "TEACHER">("STUDENT");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await register(email, password, fullName, role);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-indigo-50 flex items-center justify-center px-4 py-8">
      <div className="w-full max-w-md">
        <div className="flex justify-center mb-6">
          <Brand size="lg" />
        </div>

        <div className="bg-white rounded-2xl shadow-sm ring-1 ring-slate-200 p-7">
          <h1 className="text-xl font-semibold text-slate-900">
            Create your account
          </h1>
          <p className="text-sm text-slate-500 mt-1 mb-5">
            Pick your role to get started.
          </p>

          <form onSubmit={onSubmit} className="space-y-4">
            <fieldset>
              <legend className="text-sm font-medium text-slate-700 mb-2">
                I am a
              </legend>
              <div className="grid grid-cols-2 gap-2">
                {(
                  [
                    { value: "STUDENT", label: "Student" },
                    { value: "TEACHER", label: "Teacher" },
                  ] as const
                ).map((r) => (
                  <label
                    key={r.value}
                    className={`text-center text-sm font-medium border rounded-lg py-2.5 cursor-pointer transition-colors ${
                      role === r.value
                        ? "bg-indigo-600 text-white border-indigo-600"
                        : "bg-white text-slate-700 border-slate-300 hover:border-slate-400"
                    }`}
                  >
                    <input
                      type="radio"
                      name="role"
                      value={r.value}
                      className="sr-only"
                      checked={role === r.value}
                      onChange={() => setRole(r.value)}
                    />
                    {r.label}
                  </label>
                ))}
              </div>
            </fieldset>

            <label className="block">
              <span className="text-sm font-medium text-slate-700">
                Full name
              </span>
              <input
                autoComplete="name"
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 placeholder:text-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
                placeholder="Jane Doe"
              />
            </label>

            <label className="block">
              <span className="text-sm font-medium text-slate-700">Email</span>
              <input
                type="email"
                autoComplete="email"
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 placeholder:text-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="you@example.com"
              />
            </label>

            <PasswordInput
              label="Password"
              value={password}
              onChange={setPassword}
              required
              minLength={8}
              autoComplete="new-password"
              placeholder="At least 8 characters"
              hint="Minimum 8 characters."
            />

            {error && (
              <p className="text-sm text-rose-600 bg-rose-50 border border-rose-200 rounded-lg px-3 py-2">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={busy}
              className="w-full rounded-lg bg-indigo-600 text-white font-medium py-2.5 hover:bg-indigo-700 disabled:bg-indigo-300 transition-colors"
            >
              {busy ? "Creating account…" : "Create account"}
            </button>
          </form>

          <p className="mt-5 text-sm text-slate-600 text-center">
            Already have an account?{" "}
            <Link
              to="/login"
              className="text-indigo-600 hover:text-indigo-700 font-medium"
            >
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
