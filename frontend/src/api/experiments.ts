import apiClient from './client';
import type { PaginatedResponse } from '../types/common';
import type {
  Experiment,
  ExperimentCreate,
  ExperimentUpdate,
} from '../types/experiment';

export async function fetchExperiments(params: {
  project_id: string;
  page?: number;
  size?: number;
}): Promise<PaginatedResponse<Experiment>> {
  const { data } = await apiClient.get('/experiments', { params });
  return data;
}

export async function fetchExperiment(id: string): Promise<Experiment> {
  const { data } = await apiClient.get(`/experiments/${id}`);
  return data;
}

export async function createExperiment(
  body: ExperimentCreate
): Promise<Experiment> {
  const { data } = await apiClient.post('/experiments', body);
  return data;
}

export async function updateExperiment(
  id: string,
  body: ExperimentUpdate
): Promise<Experiment> {
  const { data } = await apiClient.put(`/experiments/${id}`, body);
  return data;
}

export async function deleteExperiment(id: string): Promise<void> {
  await apiClient.delete(`/experiments/${id}`);
}
