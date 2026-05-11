import { Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "./auth";
import { AppShell } from "./components/AppShell";
import { RoleRoute } from "./components/RoleRoute";
import { LoginPage } from "./pages/LoginPage";
import { NotificationsPage } from "./pages/NotificationsPage";
import { RegisterPage } from "./pages/RegisterPage";
import { ResultsPage } from "./pages/ResultsPage";
import { StudentAttemptsPage } from "./pages/StudentAttemptsPage";
import { StudentDashboardPage } from "./pages/StudentDashboardPage";
import { TakeQuizPage } from "./pages/TakeQuizPage";
import { TeacherDashboardPage } from "./pages/TeacherDashboardPage";
import { TeacherQuizAnalyticsPage } from "./pages/TeacherQuizAnalyticsPage";
import { TeacherQuizCreatePage } from "./pages/TeacherQuizCreatePage";
import { TeacherQuizDetailPage } from "./pages/TeacherQuizDetailPage";

function RoleHomeRedirect() {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return (
    <Navigate to={user.role === "STUDENT" ? "/student" : "/teacher"} replace />
  );
}

export function App() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center text-slate-500">
        Loading…
      </div>
    );
  }

  return (
    <Routes>
      {/* Public auth pages — no shell */}
      <Route
        path="/login"
        element={user ? <RoleHomeRedirect /> : <LoginPage />}
      />
      <Route
        path="/register"
        element={user ? <RoleHomeRedirect /> : <RegisterPage />}
      />

      {/* Authenticated pages — wrapped in AppShell */}
      <Route
        path="/*"
        element={
          user ? (
            <AppShell>
              <Routes>
                <Route path="/" element={<RoleHomeRedirect />} />

                {/* Shared (any signed-in role) */}
                <Route path="/notifications" element={<NotificationsPage />} />

                {/* Student routes */}
                <Route
                  path="/student"
                  element={
                    <RoleRoute allow={["STUDENT"]}>
                      <StudentDashboardPage />
                    </RoleRoute>
                  }
                />
                <Route
                  path="/student/attempts"
                  element={
                    <RoleRoute allow={["STUDENT"]}>
                      <StudentAttemptsPage />
                    </RoleRoute>
                  }
                />
                <Route
                  path="/student/quizzes/:quizId/take"
                  element={
                    <RoleRoute allow={["STUDENT"]}>
                      <TakeQuizPage />
                    </RoleRoute>
                  }
                />
                <Route
                  path="/student/attempts/:attemptId/results"
                  element={
                    <RoleRoute allow={["STUDENT"]}>
                      <ResultsPage />
                    </RoleRoute>
                  }
                />

                {/* Teacher routes */}
                <Route
                  path="/teacher"
                  element={
                    <RoleRoute allow={["TEACHER", "ADMIN"]}>
                      <TeacherDashboardPage />
                    </RoleRoute>
                  }
                />
                <Route
                  path="/teacher/quizzes/new"
                  element={
                    <RoleRoute allow={["TEACHER", "ADMIN"]}>
                      <TeacherQuizCreatePage />
                    </RoleRoute>
                  }
                />
                <Route
                  path="/teacher/quizzes/:quizId"
                  element={
                    <RoleRoute allow={["TEACHER", "ADMIN"]}>
                      <TeacherQuizDetailPage />
                    </RoleRoute>
                  }
                />
                <Route
                  path="/teacher/quizzes/:quizId/analytics"
                  element={
                    <RoleRoute allow={["TEACHER", "ADMIN"]}>
                      <TeacherQuizAnalyticsPage />
                    </RoleRoute>
                  }
                />

                <Route path="*" element={<RoleHomeRedirect />} />
              </Routes>
            </AppShell>
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />
    </Routes>
  );
}
