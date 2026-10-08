import * as XLSX from 'xlsx';

export const MAX_ASSISTANT_EXCEL_BYTES = 5 * 1024 * 1024;
export const DEFAULT_ASSISTANT_EXCEL_PROMPT = '请读取并概述这个 Excel 文件。';

export interface AssistantExcelFileLike {
  name: string;
  size: number;
}

export interface AssistantExcelReadable {
  arrayBuffer(): Promise<ArrayBuffer>;
}

export type AssistantFilePhase =
  | 'empty'
  | 'selected'
  | 'sending'
  | 'success'
  | 'failure';

export interface AssistantFileState<
  TFile extends AssistantExcelFileLike = AssistantExcelFileLike,
> {
  file: TFile | null;
  phase: AssistantFilePhase;
  error: string | null;
}

export function createAssistantFileState<
  TFile extends AssistantExcelFileLike = AssistantExcelFileLike,
>(): AssistantFileState<TFile> {
  return { file: null, phase: 'empty', error: null };
}

export function validateAssistantExcelFile(
  file: AssistantExcelFileLike,
): string | null {
  if (!file.name.toLowerCase().endsWith('.xlsx')) {
    return '仅支持 .xlsx 格式的 Excel 文件';
  }
  if (file.size > MAX_ASSISTANT_EXCEL_BYTES) {
    return 'Excel 文件不能超过 5 MiB';
  }
  return null;
}

export async function readAssistantExcelSheetNames(
  file: AssistantExcelReadable,
): Promise<string[]> {
  const workbook = XLSX.read(await file.arrayBuffer(), {
    type: 'array',
    bookSheets: true,
  });
  if (workbook.SheetNames.length === 0) {
    throw new Error('Excel 文件中没有可用的工作表');
  }
  return workbook.SheetNames;
}

export function selectAssistantExcelFile<TFile extends AssistantExcelFileLike>(
  state: AssistantFileState<TFile>,
  file: TFile,
): AssistantFileState<TFile> {
  const error = validateAssistantExcelFile(file);
  if (error) return { ...state, error };
  return { file, phase: 'selected', error: null };
}

export function startAssistantFileSend<TFile extends AssistantExcelFileLike>(
  state: AssistantFileState<TFile>,
): AssistantFileState<TFile> {
  if (!state.file) {
    return { ...state, error: '请先选择 Excel 文件' };
  }
  return { ...state, phase: 'sending', error: null };
}

export function succeedAssistantFileSend<TFile extends AssistantExcelFileLike>(
  state: AssistantFileState<TFile>,
): AssistantFileState<TFile> {
  if (!state.file) return state;
  return { ...state, phase: 'success', error: null };
}

export function failAssistantFileSend<TFile extends AssistantExcelFileLike>(
  state: AssistantFileState<TFile>,
  error: string,
): AssistantFileState<TFile> {
  if (!state.file) return { ...state, error };
  return { ...state, phase: 'failure', error };
}

export function removeAssistantExcelFile<TFile extends AssistantExcelFileLike>(): AssistantFileState<TFile> {
  return createAssistantFileState<TFile>();
}

export function canSendAssistantRequest(
  input: string,
  state: AssistantFileState,
): boolean {
  return state.phase !== 'sending' && (input.trim().length > 0 || state.file !== null);
}

export function buildAssistantUserContent(
  input: string,
  file: AssistantExcelFileLike | null,
): string {
  const content = input.trim();
  if (!file) return content;
  const filename = (file.name.replace(/\\/g, '/').split('/').pop() || file.name)
    .replace(/[\u0000-\u001f\u007f]/g, ' ')
    .slice(0, 120);
  const prompt = content || DEFAULT_ASSISTANT_EXCEL_PROMPT;
  return `${prompt}\n[Excel：${filename}]`;
}
