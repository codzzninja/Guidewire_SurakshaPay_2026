import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import DashboardSkeleton from "./components/DashboardSkeleton";
import { useAuth } from "./lib/AuthContext";
import DashboardPage from "./pages/DashboardPage";
import InsurerDashboardPage from "./pages/InsurerDashboardPage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";

function Protected({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) {
    return <DashboardSkeleton />;
  }
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/insurer" element={<InsurerDashboardPage />} />
      <Route
        path="/"
        element={
          <Protected>
            <DashboardPage />
          </Protected>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
