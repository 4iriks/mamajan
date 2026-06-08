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
import HardwareCatalogPage from './pages/HardwareCatalogPage';
import ToastContainer from './components/Toast';

// ── Editor Page wrapper ───────────────────────────────────────────────────────

function EditorPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  return <ProjectEditor projectId={Number(id)} onBack={() => navigate('/')} />;
}

// ── Admin Route ───────────────────────────────────────────────────────────────

function AdminRoute({ children }: { children: React.ReactNode }) {
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
        <Route path="/" element={<ProjectsPage />} />
        <Route path="/projects/:id" element={<EditorPage />} />
        <Route path="/admin" element={<AdminRoute><AdminPage /></AdminRoute>} />
        <Route path="/admin/catalog/hardware" element={<AdminRoute><HardwareCatalogPage /></AdminRoute>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}
