export interface ComparisonMaterial {
  id: string;
  name: string;
  material_type: string;
  project_id?: string;
}

export interface ComparisonMeasurement {
  id: string;
  material_id: string;
  sample_id?: string;
  property_type: string;
  property_name: string;
  value_number: number;
  uncertainty?: number;
  unit?: string;
  conditions: Record<string, unknown>;
  test_method?: string;
  created_at: string;
  measurement_count: number;
}

export interface PropertyComparison {
  materials: ComparisonMaterial[];
  measurements: ComparisonMeasurement[];
}

export interface ComparisonSample {
  id: string;
  sample_code: string;
  batch_number?: string;
  material_id?: string;
  material_name?: string;
  experiment_id?: string;
  project_id?: string;
  form?: string;
  status: string;
}

export interface SamplePropertyComparison {
  samples: ComparisonSample[];
  measurements: ComparisonMeasurement[];
}
