export interface TestMeasurement {
  id: string;
  test_id: string;
  property_name: string;
  value_number?: number;
  value_text?: string;
  unit?: string;
  created_at: string;
}

export interface MeasurementCreate {
  property_name: string;
  value_number?: number;
  value_text?: string;
  unit?: string;
}

export interface Test {
  id: string;
  material_id: string;
  test_name: string;
  test_method?: string;
  test_date?: string;
  conditions: Record<string, string>;
  notes?: string;
  metadata: Record<string, unknown>;
  measurements: TestMeasurement[];
  created_by?: string;
  created_at: string;
  updated_at: string;
}

export interface TestCreate {
  material_id: string;
  test_name: string;
  test_method?: string;
  test_date?: string;
  conditions: Record<string, string>;
  notes?: string;
  metadata: Record<string, unknown>;
  measurements: MeasurementCreate[];
}

export interface TestUpdate {
  test_name?: string;
  test_method?: string;
  test_date?: string;
  conditions?: Record<string, string>;
  notes?: string;
  metadata?: Record<string, unknown>;
}
