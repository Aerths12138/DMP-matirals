import apiClient from './client';
import type { PropertyComparison, SamplePropertyComparison } from '../types/visualization';

export async function fetchPropertyComparison(
  materialIds: string[]
): Promise<PropertyComparison> {
  const params = new URLSearchParams();
  materialIds.forEach((materialId) => params.append('material_ids', materialId));
  const { data } = await apiClient.get<PropertyComparison>('/properties/compare', { params });
  return data;
}

export async function fetchSamplePropertyComparison(
  sampleIds: string[]
): Promise<SamplePropertyComparison> {
  const params = new URLSearchParams();
  sampleIds.forEach((sampleId) => params.append('sample_ids', sampleId));
  const { data } = await apiClient.get<SamplePropertyComparison>(
    '/properties/sample-compare',
    { params }
  );
  return data;
}
