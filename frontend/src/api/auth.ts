import apiClient from './client';
import type { User } from '../types/user';

interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  const formData = new URLSearchParams();
  formData.append('username', username);
  formData.append('password', password);

  const { data } = await apiClient.post('/auth/login', formData, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });

  localStorage.setItem('access_token', data.access_token);
  localStorage.setItem('refresh_token', data.refresh_token);
  return data;
}

export async function fetchCurrentUser(): Promise<User> {
  const { data } = await apiClient.get('/auth/me');
  return data;
}

export interface RegisterBody {
  username: string;
  email: string;
  password: string;
  display_name?: string;
  department?: string;
}

export async function register(body: RegisterBody): Promise<User> {
  const { data } = await apiClient.post('/auth/register', body);
  return data;
}

export async function logout(): Promise<void> {
  const refreshToken = localStorage.getItem('refresh_token');
  if (refreshToken) {
    await apiClient.post('/auth/logout', { refresh_token: refreshToken });
  }
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
}
