import apiClient from './client';
import type { PaginatedResponse } from '../types/common';
import type {
  AnalysisResult,
  AnalysisResultCreate,
  Characterization,
  CharacterizationCreate,
  ProcessingMethod,
  ProcessingMethodCreate,
} from '../types/research';

export async function fetchProcessingMethods(params: {
  sample_id?: string;
  material_id?: string;
  page?: number;
  size?: number;
}): Promise<PaginatedResponse<ProcessingMethod>> {
  const { data } = await apiClient.get('/processing-methods', { params });
  return data;
}

export async function createProcessingMethod(
  body: ProcessingMethodCreate
): Promise<ProcessingMethod> {
  const { data } = await apiClient.post('/processing-methods', body);
  return data;
}

export async function fetchCharacterizations(params: {
  sample_id: string;
  page?: number;
  size?: number;
}): Promise<PaginatedResponse<Characterization>> {
  const { data } = await apiClient.get('/characterizations', { params });
  return data;
}

export async function createCharacterization(
  body: CharacterizationCreate
): Promise<Characterization> {
  const { data } = await apiClient.post('/characterizations', body);
  return data;
}

export async function fetchAnalysisResults(params: {
  characterization_id: string;
  latest_only?: boolean;
  page?: number;
  size?: number;
}): Promise<PaginatedResponse<AnalysisResult>> {
  const { data } = await apiClient.get('/analysis-results', { params });
  return data;
}

export async function createAnalysisResult(
  body: AnalysisResultCreate
): Promise<AnalysisResult> {
  const { data } = await apiClient.post('/analysis-results', body);
  return data;
}
