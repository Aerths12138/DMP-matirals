import apiClient from './client';
import type { ImportCell } from '../utils/importNormalization';

export type ImportMappingTarget =
  | 'name'
  | 'material_type'
  | 'formula_string'
  | 'hill_formula'
  | 'aliases'
  | 'description'
  | 'test_name'
  | 'test_method'
  | 'property'
  | 'condition'
  | 'result'
  | 'ignore';

export interface ImportAlignmentConversion {
  row: number;
  column: string;
  kind: 'numeric_text' | 'material_type';
  original: string;
  normalized: string | number;
}

export interface ImportAlignmentResponse {
  mapping: Record<string, ImportMappingTarget>;
  normalized_rows: ImportCell[][];
  conversion_count: number;
  conversions: ImportAlignmentConversion[];
  warnings: string[];
}

export async function alignImportData(body: {
  headers: string[];
  rows: ImportCell[][];
}): Promise<ImportAlignmentResponse> {
  const { data } = await apiClient.post<ImportAlignmentResponse>(
    '/assistant/import/align',
    body,
    { timeout: 30000 },
  );
  return data;
}
