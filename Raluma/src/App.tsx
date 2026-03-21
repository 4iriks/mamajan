/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useEffect } from 'react';
import { Routes, Route, Navigate, useNavigate, useParams } from 'react-router-dom';
import { ProjectEditor } from './components/ProjectEditor';
import { useAuthStore } from './store/authStore';
import { getMe } from './api/auth';
import LoginPage from './pages/LoginPage';
import ProjectsPage from './pages/ProjectsPage';
import AdminPage from './pages/AdminPage';
import ToastContainer from './components/Toast';

// ── Editor Page wrapper ───────────────────────────────────────────────────────

function EditorPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  return <ProjectEditor projectId={Number(id)} onBack={() => navigate('/')} />;
}

// ── Protected Route ───────────────────────────────────────────────────────────

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { token } = useAuthStore();
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

// ── App (Router) ──────────────────────────────────────────────────────────────

export default function App() {
  const { token, setAuth, clearAuth } = useAuthStore();

  useEffect(() => {
    if (token) {
      getMe().then(user => setAuth(token, user)).catch(() => clearAuth());
    }
  }, []);

  return (
    <>
      <ToastContainer />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<ProtectedRoute><ProjectsPage /></ProtectedRoute>} />
        <Route path="/projects/:id" element={<ProtectedRoute><EditorPage /></ProtectedRoute>} />
        <Route path="/admin" element={<ProtectedRoute><AdminPage /></ProtectedRoute>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}
