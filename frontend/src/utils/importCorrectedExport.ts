import * as XLSX from 'xlsx';

import type { ImportCell } from './importNormalization';
import type { ImportQualityIssue } from './importQuality';

function exportBaseName(originalName?: string): string {
  const baseName = originalName?.replace(/\.[^.]+$/, '').trim() || 'data';
  return baseName.replace(/[<>:"/\\|?*\u0000-\u001f]/g, '_');
}

export function correctedImportFilename(originalName?: string): string {
  return `${exportBaseName(originalName)}_corrected.xlsx`;
}

export function importQualityReportFilename(originalName?: string): string {
  return `${exportBaseName(originalName)}_quality_report.xlsx`;
}

export function createCorrectedImportWorkbook(
  headers: string[],
  rows: ImportCell[][],
  mapping: Record<string, string>,
  qualityIssues: ImportQualityIssue[] = [],
): XLSX.WorkBook {
  const correctedRows = rows.map((row) => {
    if (row.length > headers.length) {
      throw new Error('Corrected row exceeds the header width');
    }
    return headers.map((_, index) => row[index] ?? '');
  });

  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(
    workbook,
    XLSX.utils.aoa_to_sheet([headers, ...correctedRows]),
    'Corrected Data',
  );
  XLSX.utils.book_append_sheet(
    workbook,
    XLSX.utils.aoa_to_sheet([
      ['Source column', 'System field'],
      ...headers.map((header) => [header, mapping[header] || 'ignore']),
    ]),
    'Field Mapping',
  );
  XLSX.utils.book_append_sheet(
    workbook,
    XLSX.utils.aoa_to_sheet([
      ['Source row', 'Severity', 'Code', 'Column', 'Related source row', 'Message'],
      ...qualityIssues.map((issue) => [
        issue.sourceRow ?? '',
        issue.severity,
        issue.code,
        issue.column ?? '',
        issue.relatedSourceRow ?? '',
        issue.message,
      ]),
    ]),
    'Quality Report',
  );
  return workbook;
}

export function downloadCorrectedImport(
  headers: string[],
  rows: ImportCell[][],
  mapping: Record<string, string>,
  originalName?: string,
  qualityIssues: ImportQualityIssue[] = [],
): void {
  XLSX.writeFile(
    createCorrectedImportWorkbook(headers, rows, mapping, qualityIssues),
    correctedImportFilename(originalName),
  );
}

export function downloadImportQualityReport(
  headers: string[],
  rows: ImportCell[][],
  mapping: Record<string, string>,
  qualityIssues: ImportQualityIssue[],
  originalName?: string,
): void {
  XLSX.writeFile(
    createCorrectedImportWorkbook(headers, rows, mapping, qualityIssues),
    importQualityReportFilename(originalName),
  );
}
