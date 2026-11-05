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
import ConstructionPricingPage from './pages/ConstructionPricingPage';
import ToastContainer from './components/Toast';

// ── Editor Page wrapper ───────────────────────────────────────────────────────

function EditorPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  return <ProjectEditor projectId={Number(id)} onBack={() => navigate('/')} />;
}

// ── Authenticated Route ───────────────────────────────────────────────────────

function AuthenticatedRoute({ children }: { children: React.ReactNode }) {
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
        <Route path="/" element={<AuthenticatedRoute><ProjectsPage /></AuthenticatedRoute>} />
        <Route path="/projects/:id" element={<AuthenticatedRoute><EditorPage /></AuthenticatedRoute>} />
        <Route path="/admin" element={<AuthenticatedRoute><AdminPage /></AuthenticatedRoute>} />
        <Route path="/admin/catalog/hardware" element={<AuthenticatedRoute><HardwareCatalogPage /></AuthenticatedRoute>} />
        <Route path="/admin/pricing" element={<AuthenticatedRoute><ConstructionPricingPage /></AuthenticatedRoute>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}
