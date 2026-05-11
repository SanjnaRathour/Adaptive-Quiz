import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { useAuth } from "../auth";

interface RoleRouteProps {
  allow: ("STUDENT" | "TEACHER" | "ADMIN")[];
  children: ReactNode;
}

export function RoleRoute({ allow, children }: RoleRouteProps) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (!allow.includes(user.role)) {
    // Send users to whichever home matches their role.
    const target = user.role === "STUDENT" ? "/student" : "/teacher";
    return <Navigate to={target} replace />;
  }
  return <>{children}</>;
}
