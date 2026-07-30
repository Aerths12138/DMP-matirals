export type ExperimentStatus = 'planned' | 'running' | 'completed' | 'failed';
export type SampleStatus = 'created' | 'processing' | 'characterizing' | 'archived';

export interface Experiment {
  id: string;
  project_id: string;
  name: string;
  description?: string;
  hypothesis?: string;
  status: ExperimentStatus;
  start_date?: string;
  end_date?: string;
  metadata: Record<string, unknown>;
  owner_id?: string;
  created_at: string;
  updated_at: string;
}

export interface ExperimentCreate {
  project_id: string;
  name: string;
  description?: string;
  hypothesis?: string;
  status?: ExperimentStatus;
  start_date?: string;
  end_date?: string;
  metadata?: Record<string, unknown>;
}

export type ExperimentUpdate = Partial<Omit<ExperimentCreate, 'project_id'>>;

export interface Sample {
  id: string;
  experiment_id?: string;
  material_id?: string;
  sample_code: string;
  batch_number?: string;
  description?: string;
  mass_g?: number;
  dimensions: Record<string, number | string>;
  form?: string;
  storage_location?: string;
  status: SampleStatus;
  metadata: Record<string, unknown>;
  metadata_template_id?: string;
  created_by?: string;
  created_at: string;
  updated_at: string;
}

export interface SampleCreate {
  experiment_id: string;
  material_id?: string;
  sample_code: string;
  batch_number?: string;
  description?: string;
  mass_g?: number;
  dimensions?: Record<string, number | string>;
  form?: string;
  storage_location?: string;
  status?: SampleStatus;
  metadata?: Record<string, unknown>;
  metadata_template_id?: string;
}

export type SampleUpdate = Partial<Omit<SampleCreate, 'experiment_id'>>;
