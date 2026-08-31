import axios from 'axios';

// Production must always use relative /api paths through Caddy. Keeping this
// branch compile-time constant prevents a local .env.local from leaking a
// localhost backend address into an offline production build.
const BASE_URL = import.meta.env.PROD ? '' : (import.meta.env.VITE_API_URL || '');

const client = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

// Автоматически цепляем JWT токен к каждому запросу
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 401 → редирект на логин
client.interceptors.response.use(
  (response) => response,
  (error) => {
    const hadToken = Boolean(localStorage.getItem('access_token'));
    if (error.response?.status === 401 && hadToken) {
      localStorage.removeItem('access_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default client;
