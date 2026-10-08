export interface AssistantImportPreviewLike<TRow = unknown> {
  blocking_errors: string[];
  import_rows: TRow[];
}

export type AssistantImportPhase = 'empty' | 'ready' | 'importing' | 'failure';

export interface AssistantImportState<
  TPreview extends AssistantImportPreviewLike = AssistantImportPreviewLike,
> {
  preview: TPreview | null;
  phase: AssistantImportPhase;
  error: string | null;
}

export function createAssistantImportState<
  TPreview extends AssistantImportPreviewLike = AssistantImportPreviewLike,
>(): AssistantImportState<TPreview> {
  return { preview: null, phase: 'empty', error: null };
}

export function receiveAssistantImportPreview<
  TPreview extends AssistantImportPreviewLike,
>(preview: TPreview | null | undefined): AssistantImportState<TPreview> {
  if (!preview) return createAssistantImportState<TPreview>();
  return { preview, phase: 'ready', error: null };
}

export function canConfirmAssistantImport(
  state: AssistantImportState,
): boolean {
  return Boolean(
    state.preview
    && state.phase !== 'importing'
    && state.preview.blocking_errors.length === 0
    && state.preview.import_rows.length > 0,
  );
}

export function startAssistantImport<
  TPreview extends AssistantImportPreviewLike,
>(state: AssistantImportState<TPreview>): AssistantImportState<TPreview> {
  if (!canConfirmAssistantImport(state)) return state;
  return { ...state, phase: 'importing', error: null };
}

export function failAssistantImport<
  TPreview extends AssistantImportPreviewLike,
>(state: AssistantImportState<TPreview>, error: string): AssistantImportState<TPreview> {
  if (!state.preview) return { ...state, error };
  return { ...state, phase: 'failure', error };
}

export function clearAssistantImport<
  TPreview extends AssistantImportPreviewLike = AssistantImportPreviewLike,
>(): AssistantImportState<TPreview> {
  return createAssistantImportState<TPreview>();
}

export async function confirmAssistantImport<TRow, TResult>(
  state: AssistantImportState<AssistantImportPreviewLike<TRow>>,
  submit: (rows: TRow[]) => Promise<TResult>,
): Promise<TResult | null> {
  if (!canConfirmAssistantImport(state) || !state.preview) return null;
  return submit(state.preview.import_rows);
}
