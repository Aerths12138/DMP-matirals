import apiClient from './client';
import type { PaginatedResponse } from '../types/common';
import type {
  Project,
  ProjectCreate,
  ProjectMember,
  ProjectRole,
  ProjectUpdate,
} from '../types/project';

export async function fetchProjects(params?: {
  page?: number;
  size?: number;
}): Promise<PaginatedResponse<Project>> {
  const { data } = await apiClient.get('/projects', { params });
  return data;
}

export async function fetchProject(id: string): Promise<Project> {
  const { data } = await apiClient.get(`/projects/${id}`);
  return data;
}

export async function createProject(body: ProjectCreate): Promise<Project> {
  const { data } = await apiClient.post('/projects', body);
  return data;
}

export async function updateProject(
  id: string,
  body: ProjectUpdate
): Promise<Project> {
  const { data } = await apiClient.put(`/projects/${id}`, body);
  return data;
}

export async function addProjectMember(
  projectId: string,
  userId: string,
  role: Exclude<ProjectRole, 'owner'>
): Promise<ProjectMember> {
  const { data } = await apiClient.post(`/projects/${projectId}/members`, {
    user_id: userId,
    role,
  });
  return data;
}

export async function updateProjectMember(
  projectId: string,
  userId: string,
  role: Exclude<ProjectRole, 'owner'>
): Promise<ProjectMember> {
  const { data } = await apiClient.put(
    `/projects/${projectId}/members/${userId}`,
    { role }
  );
  return data;
}

export async function removeProjectMember(
  projectId: string,
  userId: string
): Promise<void> {
  await apiClient.delete(`/projects/${projectId}/members/${userId}`);
}
