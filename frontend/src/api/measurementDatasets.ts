import apiClient from './client';

export interface MeasurementSeriesInput {
  key: string;
  name: string;
  unit?: string;
}

export interface MeasurementPointInput {
  sequence: number;
  x_value: number;
  values: Record<string, number>;
}

export interface MeasurementDataset {
  id: string;
  characterization_id: string;
  source_file_id?: string;
  name: string;
  x_name: string;
  x_unit?: string;
  series_schema: MeasurementSeriesInput[];
  provenance: Record<string, unknown>;
  row_count: number;
  points: MeasurementPointInput[];
  created_at: string;
  updated_at: string;
}

export async function updateMeasurementDataset(
  id: string,
  body: Partial<Pick<MeasurementDataset, 'name' | 'x_name' | 'x_unit' | 'series_schema' | 'points' | 'provenance'>> & { source_file_id?: string },
): Promise<MeasurementDataset> {
  const { data } = await apiClient.patch(`/measurement-datasets/${id}`, body);
  return data;
}

export async function deleteMeasurementDataset(id: string): Promise<void> {
  await apiClient.delete(`/measurement-datasets/${id}`);
}

export async function createMeasurementDataset(body: {
  sample_id: string;
  name: string;
  x_name: string;
  x_unit?: string;
  series_schema: MeasurementSeriesInput[];
  points: MeasurementPointInput[];
  provenance: Record<string, unknown>;
}): Promise<MeasurementDataset> {
  const { data } = await apiClient.post('/measurement-datasets', body);
  return data;
}

export async function fetchMeasurementDatasets(sampleId: string): Promise<MeasurementDataset[]> {
  const { data } = await apiClient.get('/measurement-datasets', { params: { sample_id: sampleId } });
  return data;
}

export async function fetchMeasurementDataset(id: string): Promise<MeasurementDataset> {
  const { data } = await apiClient.get(`/measurement-datasets/${id}`);
  return data;
}
