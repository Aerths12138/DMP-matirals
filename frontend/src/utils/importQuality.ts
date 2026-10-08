import { cleanImportCell, parseImportNumber, type ImportCell } from './importNormalization.js';

export type ImportQualitySeverity = 'error' | 'warning';

export interface ImportQualityIssue {
  sourceRow?: number;
  severity: ImportQualitySeverity;
  code: 'missing_name_mapping' | 'empty_material_name' | 'duplicate_material_name' | 'mixed_numeric_text';
  column?: string;
  relatedSourceRow?: number;
  message: string;
}

export interface ImportQualitySummary {
  blockingCount: number;
  warningCount: number;
  issueCount: number;
}

function normalizedName(value: ImportCell): string {
  return cleanImportCell(value).normalize('NFKC').trim().toLocaleLowerCase().replace(/\s+/g, ' ');
}

export function analyzeImportQuality(
  headers: string[],
  rows: ImportCell[][],
  mapping: Record<string, string>,
): ImportQualityIssue[] {
  if (headers.length === 0) return [];

  const issues: ImportQualityIssue[] = [];
  const nameColumnIndex = headers.findIndex((header) => mapping[header] === 'name');
  if (nameColumnIndex < 0) {
    issues.push({
      severity: 'error',
      code: 'missing_name_mapping',
      message: '请将一列映射为材料名称。',
    });
    return issues;
  }

  const firstNameRow = new Map<string, number>();
  rows.forEach((row, rowIndex) => {
    const sourceRow = rowIndex + 2;
    const name = normalizedName(row[nameColumnIndex] ?? '');
    if (!name) {
      issues.push({
        sourceRow,
        severity: 'error',
        code: 'empty_material_name',
        column: headers[nameColumnIndex],
        message: '材料名称为空，该行不会被导入。',
      });
      return;
    }
    const existingRow = firstNameRow.get(name);
    if (existingRow !== undefined) {
      issues.push({
        sourceRow,
        severity: 'warning',
        code: 'duplicate_material_name',
        column: headers[nameColumnIndex],
        relatedSourceRow: existingRow,
        message: `材料名称与第 ${existingRow} 行重复，导入时将合并。`,
      });
    } else {
      firstNameRow.set(name, sourceRow);
    }
  });

  headers.forEach((header, columnIndex) => {
    if (!['property', 'result'].includes(mapping[header] || '')) return;
    const populated = rows
      .map((row, rowIndex) => ({ value: row[columnIndex] ?? '', sourceRow: rowIndex + 2 }))
      .filter(({ value }) => cleanImportCell(value) !== '');
    const numericCount = populated.filter(({ value }) => parseImportNumber(value) !== null).length;
    if (numericCount === 0 || numericCount === populated.length) return;
    populated
      .filter(({ value }) => parseImportNumber(value) === null)
      .forEach(({ sourceRow }) => issues.push({
        sourceRow,
        severity: 'warning',
        code: 'mixed_numeric_text',
        column: header,
        message: `列“${header}”同时包含数字和文本，请确认该文本值是否符合预期。`,
      }));
  });

  return issues;
}

export function summarizeImportQuality(issues: ImportQualityIssue[]): ImportQualitySummary {
  const blockingCount = issues.filter((issue) => issue.severity === 'error').length;
  return {
    blockingCount,
    warningCount: issues.length - blockingCount,
    issueCount: issues.length,
  };
}
