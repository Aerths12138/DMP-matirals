import apiClient from './client';
import type { PaginatedResponse } from '../types/common';
import type { GlobalSearchResult, SearchEntityType } from '../types/search';

export async function globalSearch(params: {
  q: string;
  entity_type?: SearchEntityType;
  project_id?: string;
  page?: number;
  size?: number;
}): Promise<PaginatedResponse<GlobalSearchResult>> {
  const { data } = await apiClient.get('/search', { params });
  return data;
}
