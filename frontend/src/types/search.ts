export type SearchEntityType =
  | 'project'
  | 'material'
  | 'experiment'
  | 'sample'
  | 'characterization'
  | 'file';

export interface GlobalSearchResult {
  id: string;
  entity_type: SearchEntityType;
  title: string;
  subtitle?: string;
  project_id?: string;
  parent_type?: string;
  parent_id?: string;
  updated_at: string;
}
