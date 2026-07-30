export type FileParentType =
  | 'material'
  | 'experiment'
  | 'sample'
  | 'characterization'
  | 'analysis';

export interface FileAttachment {
  id: string;
  parent_type: FileParentType;
  parent_id: string;
  original_name: string;
  storage_backend: string;
  mime_type?: string;
  file_size_bytes?: number;
  checksum_sha256?: string;
  file_type?: string;
  description?: string;
  image_width?: number;
  image_height?: number;
  tags: string[];
  uploaded_by?: string;
  created_at: string;
}

export interface FileUploadResult {
  id: string;
  original_name: string;
  mime_type?: string;
  file_size_bytes?: number;
  thumbnail_url?: string;
  download_url: string;
}
