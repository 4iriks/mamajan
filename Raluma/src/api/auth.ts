import client from './client';

export interface UserMe {
  id: number;
  username: string;
  display_name: string;
  role: 'user' | 'admin' | 'superadmin';
  customer: string | null;
  is_active: boolean;
  created_at: string;
  last_login: string | null;
}

export async function login(username: string, password: string): Promise<string> {
  const res = await client.post<{ access_token: string }>('/api/auth/login', { username, password });
  return res.data.access_token;
}

export async function getMe(): Promise<UserMe> {
  const res = await client.get<UserMe>('/api/auth/me');
  return res.data;
}
