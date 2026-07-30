import apiClient from './client';
import type { Material, MaterialCreate } from '../types/material';
import type { PaginatedResponse } from '../types/common';

// --- Import types ---

export interface ImportTestMeasurement {
  property_name: string;
  value_number?: number;
  value_text?: string;
  unit?: string;
}

export interface ImportTest {
  test_name: string;
  test_method?: string;
  conditions: Record<string, string>;
  measurements: ImportTestMeasurement[];
}

export interface ImportRow {
  name: string;
  material_type?: string;
  formula_string?: string;
  hill_formula?: string;
  aliases?: string;
  description?: string;
  properties?: Record<string, number | string>;
  tests?: ImportTest[];
}

export interface ImportRequest {
  rows: ImportRow[];
}

export interface ImportError {
  row: number;
  message: string;
}

export interface ImportResult {
  total: number;
  created: number;
  failed: number;
  errors: ImportError[];
}

export interface MaterialListParams {
  page?: number;
  size?: number;
  search?: string;
  material_type?: string;
  project_id?: string;
  sort_by?: string;
  sort_order?: string;
}

export async function fetchMaterials(params: MaterialListParams): Promise<PaginatedResponse<Material>> {
  const { data } = await apiClient.get('/materials', { params });
  return data;
}

export async function fetchMaterial(id: string): Promise<Material> {
  const { data } = await apiClient.get(`/materials/${id}`);
  return data;
}

export async function createMaterial(body: MaterialCreate): Promise<Material> {
  const { data } = await apiClient.post('/materials', body);
  return data;
}

export async function updateMaterial(id: string, body: Partial<MaterialCreate>): Promise<Material> {
  const { data } = await apiClient.put(`/materials/${id}`, body);
  return data;
}

export async function deleteMaterial(id: string): Promise<void> {
  await apiClient.delete(`/materials/${id}`);
}

export async function importMaterials(body: ImportRequest): Promise<ImportResult> {
  const { data } = await apiClient.post('/materials/import', body);
  return data;
}

export async function batchDeleteMaterials(materialIds: string[]): Promise<{ deleted: number }> {
  const { data } = await apiClient.post('/materials/batch-delete', { material_ids: materialIds });
  return data;
}

export function getExportUrl(params?: { search?: string; material_type?: string }): string {
  const base = '/materials/export/csv';
  const searchParams = new URLSearchParams();
  if (params?.search) searchParams.set('search', params.search);
  if (params?.material_type) searchParams.set('material_type', params.material_type);
  const qs = searchParams.toString();
  return qs ? `${base}?${qs}` : base;
}
