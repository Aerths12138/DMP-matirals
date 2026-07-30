export interface ProcessingMethod {
  id: string;
  material_id?: string;
  sample_id?: string;
  method_type: string;
  parameters: Record<string, unknown>;
  equipment?: string;
  description?: string;
  order_in_chain?: number;
  parent_step_id?: string;
  created_by?: string;
  created_at: string;
  updated_at: string;
}

export interface ProcessingMethodCreate {
  material_id?: string;
  sample_id?: string;
  method_type: string;
  parameters?: Record<string, unknown>;
  equipment?: string;
  description?: string;
  order_in_chain?: number;
  parent_step_id?: string;
}

export interface Characterization {
  id: string;
  sample_id: string;
  technique: string;
  title?: string;
  description?: string;
  instrument?: string;
  parameters: Record<string, unknown>;
  acquisition_date?: string;
  status: string;
  quality_flag: string;
  metadata: Record<string, unknown>;
  metadata_template_id?: string;
  operator_id?: string;
  created_by?: string;
  created_at: string;
  updated_at: string;
}

export interface CharacterizationCreate {
  sample_id: string;
  technique: string;
  title?: string;
  description?: string;
  instrument?: string;
  parameters?: Record<string, unknown>;
  acquisition_date?: string;
  status?: string;
  quality_flag?: string;
  metadata?: Record<string, unknown>;
  metadata_template_id?: string;
}

export interface AnalysisResult {
  id: string;
  characterization_id: string;
  analysis_type: string;
  pipeline_name?: string;
  model_name?: string;
  model_version?: string;
  result_data: Record<string, unknown>;
  segmentation_data?: Record<string, unknown>;
  quality_metrics: Record<string, unknown>;
  source_file_id?: string;
  processing_time_ms?: number;
  gpu_used: boolean;
  error_message?: string;
  is_latest: boolean;
  previous_version_id?: string;
  run_by?: string;
  created_at: string;
}

export interface AnalysisResultCreate {
  characterization_id: string;
  analysis_type: string;
  pipeline_name?: string;
  model_name?: string;
  model_version?: string;
  result_data?: Record<string, unknown>;
  segmentation_data?: Record<string, unknown>;
  quality_metrics?: Record<string, unknown>;
  source_file_id?: string;
  processing_time_ms?: number;
  gpu_used?: boolean;
  error_message?: string;
}
