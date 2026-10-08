export interface SavedAssistantMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface DisplayAssistantMessage extends SavedAssistantMessage {
  id: string;
}

export function assistantErrorMessage(error: any): string {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || String(item)).join('；');
  }
  if (error?.code === 'ECONNABORTED') {
    return '模型处理超过 180 秒，请稍后重试或把长文本分段发送。';
  }
  if (error?.code === 'ERR_NETWORK') {
    return '无法连接到 AI 服务，请检查后端和网络连接。';
  }
  return 'AI 助手暂时不可用，请稍后重试。';
}

export function restoreAssistantConversation(
  savedMessages: SavedAssistantMessage[],
  welcomeMessage: string,
  createId: () => string,
): DisplayAssistantMessage[] {
  const messages = savedMessages.length > 0
    ? savedMessages
    : [{ role: 'assistant' as const, content: welcomeMessage }];
  return messages.map((message) => ({ ...message, id: createId() }));
}
