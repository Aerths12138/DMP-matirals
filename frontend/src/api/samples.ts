import apiClient from './client';
import type { PaginatedResponse } from '../types/common';
import type { Sample, SampleCreate, SampleUpdate } from '../types/experiment';

export async function fetchSamples(params: {
  project_id: string;
  experiment_id?: string;
  page?: number;
  size?: number;
}): Promise<PaginatedResponse<Sample>> {
  const { data } = await apiClient.get('/samples', { params });
  return data;
}

export async function fetchSample(id: string): Promise<Sample> {
  const { data } = await apiClient.get(`/samples/${id}`);
  return data;
}

export async function createSample(body: SampleCreate): Promise<Sample> {
  const { data } = await apiClient.post('/samples', body);
  return data;
}

export async function updateSample(
  id: string,
  body: SampleUpdate
): Promise<Sample> {
  const { data } = await apiClient.put(`/samples/${id}`, body);
  return data;
}

export async function deleteSample(id: string): Promise<void> {
  await apiClient.delete(`/samples/${id}`);
}
