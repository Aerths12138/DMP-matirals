export interface Collection {
  id: string;
  name: string;
  description?: string;
  material_ids: string[];
  visibility: 'private' | 'role' | 'public';
  allowed_role_ids: number[];
  created_by?: string;
  created_at: string;
  updated_at: string;
}

export interface CollectionListItem {
  id: string;
  name: string;
  description?: string;
  visibility: 'private' | 'role' | 'public';
  material_count: number;
  created_by?: string;
  created_at: string;
}

export interface CollectionCreate {
  name: string;
  description?: string;
  material_ids: string[];
  visibility?: 'private' | 'role' | 'public';
  allowed_role_ids?: number[];
}

export interface CollectionUpdate {
  name?: string;
  description?: string;
  material_ids?: string[];
  visibility?: 'private' | 'role' | 'public';
  allowed_role_ids?: number[];
}
