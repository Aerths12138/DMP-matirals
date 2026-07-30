export type ProjectStatus = 'active' | 'completed' | 'archived';
export type ProjectRole = 'owner' | 'editor' | 'viewer';

export interface ProjectMemberUser {
  id: string;
  username: string;
  display_name?: string;
}

export interface ProjectMember {
  id: string;
  user_id: string;
  role: ProjectRole;
  created_at: string;
  updated_at: string;
  user: ProjectMemberUser;
}

export interface Project {
  id: string;
  name: string;
  description?: string;
  status: ProjectStatus;
  start_date?: string;
  end_date?: string;
  metadata: Record<string, unknown>;
  owner_id?: string;
  members: ProjectMember[];
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  name: string;
  description?: string;
  status?: ProjectStatus;
  start_date?: string;
  end_date?: string;
  metadata?: Record<string, unknown>;
}

export interface ProjectUpdate {
  name?: string;
  description?: string;
  status?: ProjectStatus;
  start_date?: string | null;
  end_date?: string | null;
  metadata?: Record<string, unknown>;
}
