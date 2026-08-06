import client from './client';

export interface UserOut {
  id: number;
  username: string;
  display_name: string;
  role: 'user' | 'dealer' | 'admin' | 'superadmin';
  customer: string | null;
  employee_number?: string | null;
  position?: string | null;
  dealer_company?: string | null;
  dealer_contact_name?: string | null;
  dealer_phone?: string | null;
  dealer_email?: string | null;
  dealer_city?: string | null;
  dealer_address?: string | null;
  dealer_inn?: string | null;
  dealer_discount_percent?: number | null;
  dealer_notes?: string | null;
  can_manage_prices: boolean;
  is_active: boolean;
  created_at: string;
  last_login: string | null;
}

export interface UserCreate {
  username: string;
  display_name: string;
  password: string;
  role: string;
  customer?: string | null;
  employee_number?: string | null;
  position?: string | null;
  dealer_company?: string | null;
  dealer_contact_name?: string | null;
  dealer_phone?: string | null;
  dealer_email?: string | null;
  dealer_city?: string | null;
  dealer_address?: string | null;
  dealer_inn?: string | null;
  dealer_discount_percent?: number | null;
  dealer_notes?: string | null;
  can_manage_prices?: boolean;
  is_active: boolean;
}

export interface UserUpdate {
  display_name?: string;
  role?: string;
  customer?: string | null;
  employee_number?: string | null;
  position?: string | null;
  dealer_company?: string | null;
  dealer_contact_name?: string | null;
  dealer_phone?: string | null;
  dealer_email?: string | null;
  dealer_city?: string | null;
  dealer_address?: string | null;
  dealer_inn?: string | null;
  dealer_discount_percent?: number | null;
  dealer_notes?: string | null;
  can_manage_prices?: boolean;
  is_active?: boolean;
  password?: string;
}

export const getUsers = () =>
  client.get<UserOut[]>('/api/users').then(r => r.data);

export const createUser = (data: UserCreate) =>
  client.post<UserOut>('/api/users', data).then(r => r.data);

export const updateUser = (id: number, data: UserUpdate) =>
  client.put<UserOut>(`/api/users/${id}`, data).then(r => r.data);

export const deleteUser = (id: number) =>
  client.delete(`/api/users/${id}`);

export const resetPassword = (id: number) =>
  client.post<{ new_password: string }>(`/api/users/${id}/reset-password`).then(r => r.data);
