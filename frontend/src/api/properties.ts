import apiClient from './client';
import type { Property, PropertyCreate } from '../types/property';
import type { PaginatedResponse } from '../types/common';

export async function fetchProperties(materialId: string): Promise<Property[]> {
  // Fetch all properties for a material (no pagination needed for detail view)
  const { data } = await apiClient.get<PaginatedResponse<Property>>('/properties', {
    params: { material_id: materialId, size: 1000 },
  });
  return data.items;
}

export async function createProperty(body: PropertyCreate): Promise<Property> {
  const { data } = await apiClient.post('/properties', body);
  return data;
}

export async function updateProperty(
  id: string,
  body: Partial<PropertyCreate>
): Promise<Property> {
  const { data } = await apiClient.put(`/properties/${id}`, body);
  return data;
}

export async function deleteProperty(id: string): Promise<void> {
  await apiClient.delete(`/properties/${id}`);
}

export async function fetchPropertyNames(): Promise<string[]> {
  const { data } = await apiClient.get('/properties/names');
  return data.names || [];
}
