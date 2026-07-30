import type { AxiosProgressEvent } from 'axios';

import apiClient from './client';
import type { PaginatedResponse } from '../types/common';
import type {
  FileAttachment,
  FileParentType,
  FileUploadResult,
} from '../types/file';

export async function fetchAttachments(params: {
  parent_type: FileParentType;
  parent_id: string;
  page?: number;
  size?: number;
}): Promise<PaginatedResponse<FileAttachment>> {
  const { data } = await apiClient.get('/files', { params });
  return data;
}

export async function uploadAttachment(
  file: File,
  params: {
    parent_type: FileParentType;
    parent_id: string;
    file_type?: string;
    description?: string;
  },
  onProgress?: (percent: number) => void
): Promise<FileUploadResult> {
  const formData = new FormData();
  formData.append('file', file);
  const { data } = await apiClient.post('/files/upload', formData, {
    params,
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 0,
    onUploadProgress: (event: AxiosProgressEvent) => {
      if (event.total) {
        onProgress?.(Math.round((event.loaded / event.total) * 100));
      }
    },
  });
  return data;
}

export async function downloadAttachment(id: string): Promise<Blob> {
  const { data } = await apiClient.get(`/files/${id}/download`, {
    responseType: 'blob',
    timeout: 0,
  });
  return data;
}

export async function deleteAttachment(id: string): Promise<void> {
  await apiClient.delete(`/files/${id}`);
}
