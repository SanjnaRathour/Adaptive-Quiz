# Adaptive Quiz

Web-based quiz platform that adapts question difficulty in real time using a
rule-based exponential-moving-average engine, and generates AI tutor feedback
on wrong answers using **Google Gemini** (free tier).

Roles: **students** take quizzes and view per-difficulty analytics; **teachers**
author and publish quizzes, manage questions, and inspect per-quiz score
distributions. Both flows are exercised end-to-end through a FastAPI backend
and a React (Vite + Tailwind v4) frontend.

## Stack

| Layer    | Tech                                                |
| -------- | --------------------------------------------------- |
| Backend  | FastAPI · SQLAlchemy 2.x · Alembic · Pydantic v2    |
| AI       | Google Gemini API (`gemini-2.5-flash` — free tier)  |
| Auth     | JWT (access + refresh) · bcrypt password hashing    |
| Database | PostgreSQL 16 (via Docker)                          |
| Frontend | React 18 · TypeScript (strict) · Vite · Tailwind v4 · TanStack Query · React Router 6 |
| Tests    | pytest + pytest-cov (66 tests, 95% coverage) · ruff lint · `tsc -b` |

## Project layout

```
backend/
  app/
    api/v1/endpoints/   FastAPI route handlers (auth, quizzes, attempts,
                        analytics, notifications)
    core/               config, database, security helpers
    models/             SQLAlchemy ORM models (8 tables)
    schemas/            Pydantic request/response schemas
    services/           business logic (adaptive engine, AI feedback,
                        attempt lifecycle, grading, analytics)
    tests/              pytest suite — 66 tests, 95% coverage
  alembic/              3 reversible migrations
  seed.py               idempotent demo data generator
  Dockerfile            backend container image
frontend/
  src/
    pages/              page components (student + teacher + shared)
    components/         shared UI (PasswordInput, NotificationBell, etc.)
    api.ts              fetch wrapper + TS types mirroring backend schemas
    auth.tsx            auth context (JWT in localStorage with silent refresh)
docker-compose.yml             Postgres + backend + frontend + (optional) adminer
Adaptive_Quiz_Project_Report.docx   Project report (64 pages)
Adaptive_Quiz_Presentation.pptx     22-slide presentation deck
```

## Reproducing from the submission zip

`Adaptive_Quiz_Submission.zip` (in the project root) ships with the full source
plus both project artefacts (DOCX + PPTX) — no committed binaries,
build outputs, virtualenvs, or `node_modules` noise. Anyone unzipping it can
rebuild the working stack with three commands:

```bash
unzip Adaptive_Quiz_Submission.zip -d adaptive-quiz && cd adaptive-quiz

docker compose up -d db                      # PostgreSQL on host port 5433
( cd backend  && python3 -m venv .venv \
                 && .venv/bin/pip install -r requirements.txt \
                 && .venv/bin/alembic upgrade head \
                 && .venv/bin/python seed.py \
                 && .venv/bin/uvicorn app.main:app --reload )
( cd frontend && npm install && npm run dev )
```

Frontend on `http://localhost:5173`, API on `http://localhost:8000`, Swagger
docs on `http://localhost:8000/docs`. Login with the demo accounts in the
table below.

## Quick start

### 1. Boot Postgres

```bash
docker compose up -d db
```

The container exposes Postgres on **host port 5433** (host port 5432 is often
already taken by a system Postgres). Connection string:

```
postgresql+psycopg2://quiz:quizpass@localhost:5433/quizdb
```

### 2. Backend

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env                    # then edit if needed
.venv/bin/alembic upgrade head          # apply schema (3 migrations)
.venv/bin/python seed.py                # seed demo accounts + quizzes (optional)
.venv/bin/uvicorn app.main:app --reload # http://localhost:8000
```

Interactive API docs: <http://localhost:8000/docs>

#### Demo accounts

`seed.py` creates the following on first run (idempotent — safe to re-run):

| Role    | Email              | Password       | What they have |
| ------- | ------------------ | -------------- | -------------- |
| Teacher | `teacher@demo.com` | `demopass123`  | 3 published quizzes (Biology, Geography, Algebra) — 20 questions across all difficulties / question types |
| Student | `student@demo.com` | `demopass123`  | One completed Biology attempt (~70 %), plus the other two for fresh attempts |

To wipe and re-seed cleanly:

```bash
.venv/bin/python seed.py --reset
```

`--reset` only deletes the two demo accounts (and cascades to their quizzes / attempts / answers / notifications) — it leaves any other data alone.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173
```

The Vite dev server proxies `/api/*` → `http://localhost:8000`, so no CORS
fiddling in dev. Production build:

```bash
npm run build   # outputs to dist/ — ~270 KB JS, ~33 KB CSS (~81 KB gzipped)
```

### 4. Enable AI feedback (optional)

Get a **free** Gemini API key at <https://aistudio.google.com/apikey>, then drop
it into `backend/.env`:

```
GOOGLE_API_KEY=AIza...
GEMINI_MODEL=gemini-2.5-flash
AI_FEEDBACK_ENABLED=true
```

`gemini-2.5-flash` has a generous free quota suitable for development and
classroom-scale demos. Without a key, the app still works — students just
don't get the AI tutor callout on wrong answers.

## Tests

```bash
cd backend
.venv/bin/pytest                            # 66 tests
.venv/bin/pytest --cov=app --cov-report=term-missing   # 95% coverage
.venv/bin/ruff check app/                   # lint
```

Tests run against a separate `quizdb_test` database that's auto-created on
first run and rolled back per-test (savepoint pattern), so they don't pollute
your dev data. AI feedback tests inject a fake Gemini client via a module-level
session factory, so they don't burn quota.

Frontend type-check + build: `cd frontend && npm run lint && npm run build`

## UI features (frontend)

- **Role-separated auth flow**: separate routes for student & teacher
  registration; route guards (`<RoleRoute>`) prevent role-leak.
- **Eye-toggle password input**: shared `<PasswordInput>` component with
  accessible `aria-pressed` toggle (used on login + register).
- **Two quiz-taking modes** driven by `Quiz.is_adaptive`:
  - **Adaptive**: one question at a time via `/next-question`; visible
    banner: "Once you submit an answer you can't go back to it."
  - **Linear**: full snapshot loaded; free Prev/Next + jump-to grid;
    upsert on every answer change; confirmation modal before final submit.
- **Indigo SmartSpend-inspired theme** applied across all pages.
- **Responsive layout**: bell dropdown uses fixed positioning on mobile,
  absolute on tablet+. Sticky question sidebar collapses below `lg`.
- **My Attempts page** (`/student/attempts`): tabbed by status, debounced
  search, paginated 10/page, Resume + Results actions.
- **Notifications**: bell dropdown shows 5 latest unread + "View all"
  link → `/notifications` (paginated 15/page, All/Unread tabs, mark-all-read).
- **Teacher dashboard**: KPI tiles, quiz list, per-quiz analytics with
  score-distribution chart, question-level accuracy table.

## Adaptive engine + AI logic

**TL;DR:**

- After every answer we update an `ability_estimate ∈ [0, 1]` per attempt
  using an EMA over difficulty-weighted outcomes:
  `new = α · outcome + (1 - α) · prior` (α = 0.4).
- Outcomes are calibrated so that *getting an EASY question right* is weak
  evidence of ability and *getting a HARD question wrong* is weak evidence
  of low ability — the asymmetry mirrors how real assessments work.
- Next-question selection draws from the unanswered, non-soft-deleted pool
  whose difficulty matches the current ability tier (`<0.4` EASY,
  `<0.75` MEDIUM, else HARD), with graceful fallback when the target tier
  is empty.
- For wrong answers we fire a FastAPI `BackgroundTask` that calls Gemini
  with a small prompt (question, student's answer, correct answer, teacher's
  note if any) and writes the response to `answers.ai_feedback`. The student
  sees a placeholder while the call runs, then the feedback appears on the
  results screen. The AI call only fires the **first** time a student gets
  the question wrong — re-answering back and forth doesn't burn quota.

## Mid-attempt safety

- Every attempt freezes its own question pool into `attempt_questions` at
  start time (a per-attempt **snapshot**).
- Questions added to the quiz afterwards don't appear in in-flight attempts.
- Soft-deleting a question (sets `questions.deleted_at`) skips it for new
  submissions in active attempts but preserves answers already submitted.
- A partial unique index
  `UNIQUE (quiz_id, student_id) WHERE status = 'IN_PROGRESS'` plus an
  `IntegrityError` retry in `start_attempt` prevents the race where two
  concurrent requests create duplicate in-progress attempts.

## API surface (high-level)

| Endpoint                                       | Role        |
| ---------------------------------------------- | ----------- |
| `POST /api/v1/auth/register`                   | public      |
| `POST /api/v1/auth/login`                      | public      |
| `POST /api/v1/auth/refresh`                    | public      |
| `GET  /api/v1/auth/me`                         | any user    |
| `POST /api/v1/quizzes`                         | teacher     |
| `GET  /api/v1/quizzes`                         | any user (filtered by role) |
| `POST /api/v1/quizzes/{id}/questions`          | teacher (own quiz) |
| `PATCH /api/v1/quizzes/questions/{id}`         | teacher (own quiz) |
| `DELETE /api/v1/quizzes/questions/{id}`        | teacher (own quiz) — **soft delete** |
| `POST /api/v1/quizzes/{id}/publish`            | teacher (own quiz) |
| `POST /api/v1/quizzes/{id}/attempts`           | student     |
| `GET  /api/v1/attempts`                        | student (paginated, `?status=&search=&page=&page_size=`) |
| `GET  /api/v1/attempts/{id}/next-question`     | student (own attempt; adaptive pick) |
| `GET  /api/v1/attempts/{id}/questions`         | student (own attempt; full snapshot for Prev/Next UI) |
| `POST /api/v1/attempts/{id}/answers`           | student (own attempt; **upsert** — re-submit updates) |
| `POST /api/v1/attempts/{id}/complete`          | student (own attempt) |
| `GET  /api/v1/attempts/{id}/results`           | student (own) / teacher / admin |
| `GET  /api/v1/analytics/me`                    | student     |
| `GET  /api/v1/analytics/overview`              | teacher     |
| `GET  /api/v1/analytics/quizzes/{id}`          | teacher (own quiz) |
| `GET  /api/v1/notifications`                   | any user (paginated) |
| `POST /api/v1/notifications/{id}/read`         | any user (own) |
| `POST /api/v1/notifications/read-all`          | any user (bulk mark unread → read) |

Full schemas at `/docs` (OpenAPI / Swagger UI).

## Project artefacts

| File                                       | Notes |
| ------------------------------------------ | ----- |
| `Adaptive_Quiz_Project_Report.docx`        | Full project report — 64 pages, 29 figures (DFDs, UML, ER, sequence, activity, wireframes, screenshots). |
| `Adaptive_Quiz_Project_Report.pdf`         | PDF export of the report — same content, ready for viewing without Word. |
| `Adaptive_Quiz_Presentation.pptx`          | 22-slide deck with title, agenda, architecture diagrams, technical detail, and comparison table. |

## Notes & tradeoffs

- **AI feedback is async**: `submit_answer` does not block on Gemini. The
  student sees `is_correct` immediately; feedback arrives on the results
  page (which polls briefly). Only fires on **first** wrong submission per
  question.
- **Soft delete only**: `DELETE /api/v1/quizzes/questions/{id}` sets
  `deleted_at` rather than removing the row, so historical attempts and
  per-question analytics keep resolving forever.
- **Notifications** are currently in-app only (no email/push). The model is
  ready for it; just add a sender service.
- **Scheduled quizzes**: `Quiz.scheduled_at` exists on the model but isn't
  yet used to fire `QUIZ_SCHEDULED` notifications — that needs a periodic
  job (e.g. APScheduler/celery beat or a cron-driven script).
- **Adaptive engine** uses a simple EMA rather than full IRT (Item Response
  Theory). IRT would be more statistically rigorous but requires a calibration
  dataset that doesn't exist for a fresh classroom-scale deployment. Switching
  to IRT later is straightforward — the engine is isolated in `services/adaptive.py`.
