import type { ImportAlignmentResponse } from '../api/importAlignment';
import type { ImportCell } from './importNormalization';

export interface ImportAlignmentViewState {
  rows: ImportCell[][];
  columnMapping: Record<string, string>;
  alignmentResult: ImportAlignmentResponse | null;
  alignmentError: string | null;
}

export function applyImportAlignmentSuccess(
  state: ImportAlignmentViewState,
  result: ImportAlignmentResponse,
): ImportAlignmentViewState {
  return {
    ...state,
    rows: result.normalized_rows,
    columnMapping: result.mapping,
    alignmentResult: result,
    alignmentError: null,
  };
}

export function applyImportAlignmentFailure(
  state: ImportAlignmentViewState,
  error: string,
): ImportAlignmentViewState {
  return {
    ...state,
    alignmentResult: null,
    alignmentError: error,
  };
}

export function confirmImport(submit: () => void, canSubmit = true): boolean {
  if (!canSubmit) return false;
  submit();
  return true;
}
