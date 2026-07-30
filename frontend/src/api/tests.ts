import apiClient from './client';
import type { Test, TestCreate, TestUpdate, TestMeasurement, MeasurementCreate } from '../types/test';
import type { PaginatedResponse } from '../types/common';

export interface TestListParams {
  material_id?: string;
  page?: number;
  size?: number;
}

export async function fetchTests(params: TestListParams): Promise<PaginatedResponse<Test>> {
  const { data } = await apiClient.get('/tests', { params });
  return data;
}

export async function fetchTest(id: string): Promise<Test> {
  const { data } = await apiClient.get(`/tests/${id}`);
  return data;
}

export async function createTest(body: TestCreate): Promise<Test> {
  const { data } = await apiClient.post('/tests', body);
  return data;
}

export async function updateTest(id: string, body: TestUpdate): Promise<Test> {
  const { data } = await apiClient.put(`/tests/${id}`, body);
  return data;
}

export async function deleteTest(id: string): Promise<void> {
  await apiClient.delete(`/tests/${id}`);
}

export async function addMeasurement(
  testId: string,
  body: MeasurementCreate
): Promise<TestMeasurement> {
  const { data } = await apiClient.post(`/tests/${testId}/measurements`, body);
  return data;
}

export async function updateMeasurement(
  testId: string,
  measurementId: string,
  body: Partial<MeasurementCreate>
): Promise<TestMeasurement> {
  const { data } = await apiClient.put(`/tests/${testId}/measurements/${measurementId}`, body);
  return data;
}

export async function deleteMeasurement(
  testId: string,
  measurementId: string
): Promise<void> {
  await apiClient.delete(`/tests/${testId}/measurements/${measurementId}`);
}

// --- Batch operations ---

export interface BatchMergeRequest {
  test_ids: string[];
  target_name?: string;
  target_method?: string;
}

export async function batchDeleteTests(testIds: string[]): Promise<void> {
  await apiClient.post('/tests/batch-delete', { test_ids: testIds });
}

export async function batchMergeTests(body: BatchMergeRequest): Promise<Test> {
  const { data } = await apiClient.post('/tests/batch-merge', body);
  return data;
}
