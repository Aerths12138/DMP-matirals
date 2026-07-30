import apiClient from './client';
import type { Collection, CollectionListItem, CollectionCreate, CollectionUpdate } from '../types/collection';
import type { PaginatedResponse } from '../types/common';

export async function fetchCollections(params?: {
  page?: number;
  size?: number;
}): Promise<PaginatedResponse<CollectionListItem>> {
  const { data } = await apiClient.get('/collections', { params });
  return data;
}

export async function fetchCollection(id: string): Promise<Collection> {
  const { data } = await apiClient.get(`/collections/${id}`);
  return data;
}

export async function createCollection(body: CollectionCreate): Promise<Collection> {
  const { data } = await apiClient.post('/collections', body);
  return data;
}

export async function updateCollection(id: string, body: CollectionUpdate): Promise<Collection> {
  const { data } = await apiClient.put(`/collections/${id}`, body);
  return data;
}

export async function deleteCollection(id: string): Promise<void> {
  await apiClient.delete(`/collections/${id}`);
}

export async function addMaterialsToCollection(
  id: string,
  materialIds: string[]
): Promise<Collection> {
  const { data } = await apiClient.post(`/collections/${id}/add-materials`, {
    material_ids: materialIds,
  });
  return data;
}
