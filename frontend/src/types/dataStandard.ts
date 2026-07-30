export type MetadataEntityType = 'sample' | 'characterization';
export type MetadataValueType = 'string' | 'number' | 'integer' | 'boolean';

export interface MetadataFieldDefinition {
  key: string;
  label: string;
  value_type: MetadataValueType;
  required: boolean;
  unit?: string;
  options: string[];
  description?: string;
}

export interface MetadataTemplate {
  id: string;
  project_id: string;
  name: string;
  entity_type: MetadataEntityType;
  description?: string;
  fields: MetadataFieldDefinition[];
  is_active: boolean;
  created_by?: string;
  created_at: string;
  updated_at: string;
}

export interface MetadataTemplateCreate {
  project_id: string;
  name: string;
  entity_type: MetadataEntityType;
  description?: string;
  fields: MetadataFieldDefinition[];
}

export interface MetadataTemplateUpdate {
  name?: string;
  description?: string;
  fields?: MetadataFieldDefinition[];
  is_active?: boolean;
}

export interface UnitDefinition {
  id: string;
  project_id?: string;
  symbol: string;
  name: string;
  quantity_type: string;
  description?: string;
  is_active: boolean;
  is_builtin: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface UnitDefinitionCreate {
  project_id: string;
  symbol: string;
  name: string;
  quantity_type: string;
  description?: string;
}
