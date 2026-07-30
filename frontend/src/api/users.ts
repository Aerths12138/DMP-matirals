import apiClient from './client';
import type { User, UserDirectoryItem } from '../types/user';
import type { PaginatedResponse } from '../types/common';

export async function fetchUsers(params: {
  page?: number;
  size?: number;
  search?: string;
  is_active?: boolean;
  is_approved?: boolean;
}): Promise<PaginatedResponse<User>> {
  const { data } = await apiClient.get('/users', { params });
  return data;
}

export async function createUser(body: {
  username: string;
  email: string;
  password: string;
  display_name?: string;
  department?: string;
}): Promise<User> {
  const { data } = await apiClient.post('/users', body);
  return data;
}

export async function updateUser(
  id: string,
  body: Record<string, unknown>
): Promise<User> {
  const { data } = await apiClient.put(`/users/${id}`, body);
  return data;
}

export async function deleteUser(id: string): Promise<void> {
  await apiClient.delete(`/users/${id}`);
}

export async function changeUserRole(id: string, role_id: number): Promise<void> {
  await apiClient.patch(`/users/${id}/role`, { role_id });
}

export async function approveUser(id: string, role_id: number): Promise<void> {
  await apiClient.patch(`/users/${id}/approve`, { role_id });
}

export async function fetchRoles(): Promise<Array<{ id: number; name: string; description?: string }>> {
  const { data } = await apiClient.get('/users/roles/list');
  return data;
}

export async function fetchUserDirectory(): Promise<UserDirectoryItem[]> {
  const { data } = await apiClient.get('/users/directory');
  return data;
}
