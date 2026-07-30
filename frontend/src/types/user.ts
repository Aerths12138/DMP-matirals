export interface User {
  id: string;
  username: string;
  email: string;
  display_name?: string;
  is_active: boolean;
  is_approved: boolean;
  role_id?: number;
  role_name?: string;
  department?: string;
  created_at: string;
}

export interface Role {
  id: number;
  name: string;
  description?: string;
}

export interface UserDirectoryItem {
  id: string;
  username: string;
  display_name?: string;
  department?: string;
}
