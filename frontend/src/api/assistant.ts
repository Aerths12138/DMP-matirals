import apiClient from './client';
import type { ImportRow } from './materials';
import type { ImportAlignmentResponse } from './importAlignment';

export const ASSISTANT_CHAT_TIMEOUT_MS = 180000;

export type AssistantRole = 'user' | 'assistant';

export interface AssistantMessage {
  role: AssistantRole;
  content: string;
}

export interface PendingAssistantAction {
  token: string;
  tool_name: string;
  operation: 'create' | 'update' | 'delete';
  entity_type: 'material' | 'project' | 'experiment' | 'sample' | 'property' | 'test' | 'test_measurement' | 'characterization';
  summary: string;
  arguments: Record<string, unknown>;
  expires_at: string;
}

export interface AssistantBackup {
  id: string;
  operation: 'update' | 'delete';
  entity_type: 'material' | 'project' | 'experiment' | 'sample' | 'property' | 'test' | 'test_measurement' | 'characterization';
  entity_id: string;
  entity_name: string;
  summary: string;
  created_at: string;
  expires_at: string;
  restored_at: string | null;
}

export interface AssistantAnalysisGroup {
  label: string;
  unit: string;
  count: number;
  mean: number | null;
  median: number | null;
  min: number | null;
  max: number | null;
  std_dev: number | null;
  outlier_count: number;
}

export interface AssistantAnalysisCard {
  analysis_id: string;
  title: string;
  metric: string;
  groups: AssistantAnalysisGroup[];
  quality: {
    records_returned: number;
    numeric_records: number;
    missing_numeric_records: number;
    unit_groups: string[];
    condition_variants: number;
    test_method_variants: number;
    outlier_count: number;
    outlier_method: string;
    truncated: boolean;
  };
  provenance: {
    generated_at: string;
    record_references: Array<Record<string, unknown>>;
    record_references_truncated: boolean;
  };
  query_plan: Record<string, unknown>;
  limitations: string[];
  chart: {
    type: 'mean_bar';
    x_label: string;
    y_label: string;
    points: Array<{ label: string; mean: number | null; count: number; unit: string }>;
  };
}

export interface AssistantKnowledgeCitation {
  file_id: string;
  file_name: string;
  parent_type: string;
  parent_id: string;
  download_url: string;
  chunk_index: number;
  page_start: number | null;
  page_end: number | null;
  source_type: string;
  source_metadata: Record<string, unknown>;
}

export interface AssistantKnowledgeCard {
  query: string;
  items: Array<{
    score: number;
    excerpt: string;
    citation: AssistantKnowledgeCitation;
  }>;
  retrieval: {
    engine: string;
    version: string;
    semantic_embeddings: boolean;
    candidate_chunks_checked: number;
    visible_candidate_chunks: number;
    returned: number;
    scope: string;
  };
  limitations: string[];
}

export interface AssistantChatResponse {
  message: string;
  pending_actions: PendingAssistantAction[];
  pending_import?: AssistantImportPreview | null;
  analysis_cards: AssistantAnalysisCard[];
  knowledge_cards: AssistantKnowledgeCard[];
  model: string;
}

export interface AssistantImportPreview extends ImportAlignmentResponse {
  filename: string;
  sheet_name: string;
  source_row_count: number;
  material_count: number;
  blocking_errors: string[];
  import_rows: ImportRow[];
}

export interface AssistantHistoryResponse {
  messages: AssistantMessage[];
  updated_at: string | null;
}

export interface AssistantActionConfirmResponse {
  message: string;
  entity_type: 'material' | 'project' | 'experiment' | 'sample' | 'property' | 'test' | 'test_measurement' | 'characterization';
  entity_id: string | null;
  data: Record<string, unknown>;
  backup: AssistantBackup | null;
}

export interface AssistantBackupRestoreResponse {
  message: string;
  backup_id: string;
  entity_type: 'material' | 'project' | 'experiment' | 'sample' | 'property' | 'test' | 'test_measurement' | 'characterization';
  entity_id: string;
}

export async function chatWithAssistant(
  messages: AssistantMessage[],
  contextPath?: string,
): Promise<AssistantChatResponse> {
  const { data } = await apiClient.post<AssistantChatResponse>(
    '/assistant/chat',
    { messages, context_path: contextPath },
    { timeout: ASSISTANT_CHAT_TIMEOUT_MS },
  );
  return data;
}

export async function chatWithAssistantExcel(
  messages: AssistantMessage[],
  file: File,
  contextPath?: string,
  sheetName?: string,
): Promise<AssistantChatResponse> {
  const formData = new FormData();
  formData.append('request', JSON.stringify({ messages, context_path: contextPath }));
  formData.append('file', file);
  if (sheetName) formData.append('sheet_name', sheetName);
  const { data } = await apiClient.post<AssistantChatResponse>(
    '/assistant/chat/excel',
    formData,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: ASSISTANT_CHAT_TIMEOUT_MS,
    },
  );
  return data;
}

export async function getAssistantHistory(): Promise<AssistantHistoryResponse> {
  const { data } = await apiClient.get<AssistantHistoryResponse>('/assistant/history');
  return data;
}

export async function clearAssistantHistory(): Promise<void> {
  await apiClient.delete('/assistant/history');
}

export async function confirmAssistantAction(
  token: string,
): Promise<AssistantActionConfirmResponse> {
  const { data } = await apiClient.post<AssistantActionConfirmResponse>(
    '/assistant/actions/confirm',
    { token },
    { timeout: 30000 },
  );
  return data;
}

export async function listAssistantBackups(): Promise<AssistantBackup[]> {
  const { data } = await apiClient.get<AssistantBackup[]>('/assistant/backups');
  return data;
}

export async function restoreAssistantBackup(
  backupId: string,
): Promise<AssistantBackupRestoreResponse> {
  const { data } = await apiClient.post<AssistantBackupRestoreResponse>(
    `/assistant/backups/${backupId}/restore`,
    undefined,
    { timeout: 30000 },
  );
  return data;
}
