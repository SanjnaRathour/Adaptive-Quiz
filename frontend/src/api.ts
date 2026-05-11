/** Thin fetch wrapper. Pulls the access token from localStorage. */

const API_BASE = "/api/v1";

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(detail);
  }
}

function getToken(): string | null {
  return localStorage.getItem("access_token");
}

export async function api<T>(
  path: string,
  init: RequestInit & { json?: unknown } = {},
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string> | undefined),
  };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const body = init.json !== undefined ? JSON.stringify(init.json) : init.body;
  const resp = await fetch(`${API_BASE}${path}`, { ...init, headers, body });
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const j = await resp.json();
      detail = j.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(resp.status, detail);
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

// ----- Domain types (mirror backend Pydantic schemas) -----

export type UserRole = "STUDENT" | "TEACHER" | "ADMIN";
export type Difficulty = "EASY" | "MEDIUM" | "HARD";
export type AttemptStatus = "IN_PROGRESS" | "COMPLETED" | "ABANDONED";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface QuizSummary {
  id: string;
  title: string;
  description: string | null;
  subject: string;
  is_published: boolean;
  is_adaptive: boolean;
  duration_minutes: number;
  passing_score: number;
  question_count: number;
  created_by_id: string;
  scheduled_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface QuestionStudentRead {
  id: string;
  text: string;
  type: "MULTIPLE_CHOICE" | "TRUE_FALSE" | "SHORT_ANSWER";
  difficulty: Difficulty;
  points: number;
  options: { id: string; text: string; order_index: number }[];
}

export interface NextQuestionResponse {
  question: QuestionStudentRead | null;
  remaining: number;
}

export interface AttemptRead {
  id: string;
  quiz_id: string;
  student_id: string;
  status: AttemptStatus;
  started_at: string | null;
  completed_at: string | null;
  score: number | null;
  ability_estimate: number;
}

export interface AttemptResultDetail {
  question_id: string;
  question_text: string;
  difficulty: Difficulty;
  points: number;
  your_answer: string | null;
  correct_answer: string | null;
  is_correct: boolean | null;
  explanation: string | null;
  ai_feedback: string | null;
}

export interface AttemptResults {
  attempt: AttemptRead;
  total_questions: number;
  correct_count: number;
  details: AttemptResultDetail[];
}

export interface StudentDashboard {
  total_attempts: number;
  completed_attempts: number;
  in_progress_attempts: number;
  average_score: number | null;
  accuracy_by_difficulty: {
    difficulty: Difficulty;
    answered: number;
    correct: number;
    accuracy: number;
  }[];
  recent_attempts: {
    attempt_id: string;
    quiz_id: string;
    quiz_title: string;
    status: AttemptStatus;
    score: number | null;
    completed_at: string | null;
  }[];
}

export interface TeacherOverview {
  quizzes_authored: number;
  quizzes_published: number;
  total_student_attempts: number;
  average_score_across_quizzes: number | null;
}

export interface NotificationRead {
  id: string;
  type: string;
  title: string;
  message: string;
  related_quiz_id: string | null;
  read_at: string | null;
  created_at: string;
}

export interface PaginatedNotifications {
  items: NotificationRead[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
  unread_count: number;
}

// ----- Teacher-side types -----

export type QuestionType = "MULTIPLE_CHOICE" | "TRUE_FALSE" | "SHORT_ANSWER";

export interface QuestionOptionTeacher {
  id: string;
  text: string;
  is_correct: boolean;
  order_index: number;
}

export interface QuestionTeacherRead {
  id: string;
  quiz_id: string;
  text: string;
  type: QuestionType;
  difficulty: Difficulty;
  explanation: string | null;
  correct_text_answer: string | null;
  points: number;
  order_index: number;
  options: QuestionOptionTeacher[];
}

export interface QuizCreatePayload {
  title: string;
  description?: string | null;
  subject: string;
  is_adaptive?: boolean;
  duration_minutes?: number;
  passing_score?: number;
}

export interface QuestionOptionPayload {
  text: string;
  is_correct: boolean;
  order_index: number;
}

export interface QuestionCreatePayload {
  text: string;
  type: QuestionType;
  difficulty: Difficulty;
  explanation?: string | null;
  correct_text_answer?: string | null;
  points?: number;
  order_index?: number;
  options: QuestionOptionPayload[];
}

export interface ScoreBucket {
  label: string;
  count: number;
}

export interface QuestionStat {
  question_id: string;
  question_text: string;
  difficulty: Difficulty;
  times_answered: number;
  times_correct: number;
  accuracy: number;
}

export interface QuizAnalytics {
  quiz_id: string;
  title: string;
  total_attempts: number;
  completed_attempts: number;
  average_score: number | null;
  score_distribution: ScoreBucket[];
  question_stats: QuestionStat[];
}

export interface AttemptQuestionItem {
  question: QuestionStudentRead;
  selected_option_id: string | null;
  text_answer: string | null;
  is_correct: boolean | null;
}

export interface AttemptListItem {
  id: string;
  quiz_id: string;
  quiz_title: string;
  quiz_subject: string;
  quiz_author: string;
  quiz_author_email: string;
  status: AttemptStatus;
  score: number | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface PaginatedAttempts {
  items: AttemptListItem[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
}
