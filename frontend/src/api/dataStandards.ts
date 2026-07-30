import apiClient from './client';
import type {
  MetadataEntityType,
  MetadataTemplate,
  MetadataTemplateCreate,
  MetadataTemplateUpdate,
  UnitDefinition,
  UnitDefinitionCreate,
} from '../types/dataStandard';

export async function fetchMetadataTemplates(params: {
  project_id: string;
  entity_type?: MetadataEntityType;
  active_only?: boolean;
}): Promise<MetadataTemplate[]> {
  const { data } = await apiClient.get('/data-standards/templates', { params });
  return data;
}

export async function createMetadataTemplate(
  body: MetadataTemplateCreate
): Promise<MetadataTemplate> {
  const { data } = await apiClient.post('/data-standards/templates', body);
  return data;
}

export async function updateMetadataTemplate(
  id: string,
  body: MetadataTemplateUpdate
): Promise<MetadataTemplate> {
  const { data } = await apiClient.put(`/data-standards/templates/${id}`, body);
  return data;
}

export async function fetchUnitDefinitions(
  projectId: string
): Promise<UnitDefinition[]> {
  const { data } = await apiClient.get('/data-standards/units', {
    params: { project_id: projectId },
  });
  return data;
}

export async function createUnitDefinition(
  body: UnitDefinitionCreate
): Promise<UnitDefinition> {
  const { data } = await apiClient.post('/data-standards/units', body);
  return data;
}
