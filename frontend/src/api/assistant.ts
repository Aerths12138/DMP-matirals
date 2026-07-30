import apiClient from './client';

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

export interface AssistantChatResponse {
  message: string;
  pending_actions: PendingAssistantAction[];
  model: string;
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
    { timeout: 60000 },
  );
  return data;
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
