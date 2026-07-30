export interface Property {
  id: string;
  material_id: string;
  sample_id?: string;
  property_type?: string;
  property_name: string;
  value_number?: number;
  value_text?: string;
  uncertainty?: number;
  unit?: string;
  conditions?: Record<string, unknown>;
  test_method?: string;
  source_type?: string;
  source_doi?: string;
  notes?: string;
  is_validated?: boolean;
  created_by?: string;
  created_at: string;
  updated_at: string;
}

export interface PropertyCreate {
  material_id: string;
  property_name: string;
  property_type?: string;
  value_number?: number;
  value_text?: string;
  unit?: string;
  test_method?: string;
  conditions?: Record<string, unknown>;
  notes?: string;
  metadata?: Record<string, unknown>;
}
