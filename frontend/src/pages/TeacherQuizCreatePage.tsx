import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api } from "../api";
import type { QuizCreatePayload, QuizSummary } from "../api";

export function TeacherQuizCreatePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [duration, setDuration] = useState(30);
  const [passingScore, setPassingScore] = useState(60);
  const [isAdaptive, setIsAdaptive] = useState(true);
  const [scheduledAt, setScheduledAt] = useState("");

  const create = useMutation({
    mutationFn: (payload: QuizCreatePayload) =>
      api<QuizSummary>("/quizzes", { method: "POST", json: payload }),
    onSuccess: (quiz) => {
      queryClient.invalidateQueries({ queryKey: ["quizzes"] });
      queryClient.invalidateQueries({ queryKey: ["teacher-overview"] });
      navigate(`/teacher/quizzes/${quiz.id}`);
    },
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate({
      title: title.trim(),
      subject: subject.trim(),
      description: description.trim() || null,
      duration_minutes: duration,
      passing_score: passingScore,
      is_adaptive: isAdaptive,
      scheduled_at: scheduledAt ? new Date(scheduledAt).toISOString() : null,
    });
  };

  return (
    <div className="max-w-xl">
      <Link
        to="/teacher"
        className="text-sm text-slate-600 hover:text-slate-900"
      >
        ← Back to dashboard
      </Link>
      <h2 className="text-lg font-semibold mt-2 mb-4">Create a new quiz</h2>

      <form
        onSubmit={onSubmit}
        className="space-y-4 bg-white border border-slate-200 rounded-lg p-5"
      >
        <label className="block">
          <span className="text-sm text-slate-700">Title</span>
          <input
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            maxLength={255}
          />
        </label>

        <label className="block">
          <span className="text-sm text-slate-700">Subject</span>
          <input
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            required
            maxLength={100}
            placeholder="e.g. Math, History, Biology"
          />
        </label>

        <label className="block">
          <span className="text-sm text-slate-700">
            Description <span className="text-slate-400">(optional)</span>
          </span>
          <textarea
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </label>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <label className="block">
            <span className="text-sm text-slate-700">Duration (minutes)</span>
            <input
              type="number"
              min={1}
              max={600}
              className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
              value={duration}
              onChange={(e) => setDuration(Number(e.target.value))}
              required
            />
          </label>
          <label className="block">
            <span className="text-sm text-slate-700">Passing score (%)</span>
            <input
              type="number"
              min={0}
              max={100}
              className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
              value={passingScore}
              onChange={(e) => setPassingScore(Number(e.target.value))}
              required
            />
          </label>
        </div>

        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={isAdaptive}
            onChange={(e) => setIsAdaptive(e.target.checked)}
          />
          Adaptive difficulty (AI picks next question based on performance)
        </label>

        <label className="block">
          <span className="text-sm text-slate-700">
            Schedule date &amp; time{" "}
            <span className="text-slate-400">(optional — students are notified when set)</span>
          </span>
          <input
            type="datetime-local"
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
            value={scheduledAt}
            onChange={(e) => setScheduledAt(e.target.value)}
          />
        </label>

        {create.isError && (
          <p className="text-sm text-rose-600">
            {(create.error as Error)?.message ?? "Failed to create quiz"}
          </p>
        )}

        <div className="flex gap-2">
          <button
            type="submit"
            disabled={create.isPending}
            className="bg-indigo-600 text-white rounded-lg px-4 py-2 hover:bg-indigo-700 disabled:bg-indigo-300 disabled:cursor-not-allowed"
          >
            {create.isPending ? "Creating…" : "Create quiz"}
          </button>
          <Link
            to="/teacher"
            className="text-slate-700 px-4 py-2 hover:text-slate-900"
          >
            Cancel
          </Link>
        </div>
      </form>
    </div>
  );
}
