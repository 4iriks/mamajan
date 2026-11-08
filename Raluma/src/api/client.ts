import axios from 'axios';

// Production must always use relative /api paths through Caddy. Keeping this
// branch compile-time constant prevents a local .env.local from leaking a
// localhost backend address into an offline production build.
const viteEnv = import.meta.env as ImportMetaEnv | undefined;
const BASE_URL = viteEnv?.PROD ? '' : (viteEnv?.VITE_API_URL || '');

const versions = new Map<number, number>();
export const projectVersion = (id: number) => versions.get(id);
const projectIdFromUrl = (url?: string) => Number(url?.match(/\/api\/projects\/(\d+)(?:\/|$)/)?.[1]);
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
  const version = versions.get(projectIdFromUrl(config.url));
  if (version !== undefined && config.method !== 'get') config.headers['X-Project-Version'] = String(version);
  return config;
});

// 401 → редирект на логин
client.interceptors.response.use(
  (response) => {
    const id = projectIdFromUrl(response.config.url);
    const version = response.data?.workflow?.version ?? response.headers['x-project-version'];
    if (id && version != null) versions.set(id, Number(version));
    if (response.config.url === '/api/projects' && Array.isArray(response.data)) {
      response.data.forEach(p => { if (p.workflow?.version) versions.set(p.id, p.workflow.version); });
    }
    return response;
  },
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
