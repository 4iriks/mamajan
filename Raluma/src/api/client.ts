import axios from 'axios';

// Local development gets the backend URL from .env.local. In production an
// empty value intentionally keeps requests on the current origin so Caddy can
// proxy /api to the backend container.
const BASE_URL = import.meta.env.VITE_API_URL || '';

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
