export type AssistantActionStatus =
  | 'pending'
  | 'executing'
  | 'completed'
  | 'cancelled';

export function updateAssistantActionStatus<
  T extends { token: string; status: AssistantActionStatus },
>(
  actions: readonly T[],
  token: string,
  status: AssistantActionStatus,
): T[] {
  return actions.map((action) =>
    action.token === token ? { ...action, status } : action,
  );
}

export function canConfirmAssistantAction(status: AssistantActionStatus): boolean {
  return status === 'pending';
}
