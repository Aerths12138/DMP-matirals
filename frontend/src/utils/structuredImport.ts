import { parseImportNumber, type ImportCell } from './importNormalization.js';

export interface StructuredColumn {
  key: string;
  name: string;
  unit?: string;
  sourceColumn: number;
}

export interface ExcludedStructuredRow {
  sourceRow: number;
  label: string;
  reason: 'derived_summary';
}

export interface StructuredMetadataItem {
  sourceRow: number;
  name: string;
  value: string;
  unit?: string;
}

export interface StructuredDatasetPreview {
  kind: 'measurement_dataset';
  title: string;
  headerRow: number;
  unitRow?: number;
  columns: StructuredColumn[];
  rows: ImportCell[][];
  sourceRows: number[];
  excludedRows: ExcludedStructuredRow[];
  metadata: StructuredMetadataItem[];
  suggestedSeriesColumnIndexes: number[];
  xColumnIndex: number;
  warnings: string[];
}

const DERIVED_LABELS = new Set([
  '变异系数', '标准方差', '标准差', '方差', '最大值', '最小值', '平均值', '均值',
  '中位数', '合计', '总计', 'cv', 'coefficientofvariation', 'variance',
  'standarddeviation', 'stddev', 'maximum', 'minimum', 'mean', 'average', 'median',
]);

const MATERIAL_NAME_HEADERS = new Set([
  '名称', '材料名称', '样品名称', 'name', 'material', 'materialname', 'samplename',
]);

const UNIT_TOKEN = /^(?:%|s|ms|min|h|pa|kpa|mpa|gpa|n|mn|μn|nm|μm|mm|cm|m|v|kv|a|ma|μa|ω|kω|mω|°|°c|℃|k|hz|khz|mhz|ghz|μnm)$/i;

const DERIVED_COLUMN_KEYWORDS = [
  '密度', 'density', '电阻', 'resistance', '电阻率', 'resistivity', '电导率', 'conductivity',
  'u/i', '比值', 'ratio',
];

function text(value: unknown): string {
  return value == null ? '' : String(value).trim();
}

function normalized(value: unknown): string {
  return text(value).normalize('NFKC').toLowerCase().replace(/[\s_\-:：()（）\[\]【】]/g, '');
}

function nonEmptyCount(row: ImportCell[]): number {
  return row.filter((value) => text(value) !== '').length;
}

function numericRatio(row: ImportCell[], columns?: number[]): number {
  const indexes = columns || row.map((_, index) => index);
  const values = indexes.map((index) => row[index]).filter((value) => text(value) !== '');
  if (values.length === 0) return 0;
  return values.filter((value) => parseImportNumber(value) !== null).length / values.length;
}

function parseUnitCell(value: ImportCell): string | undefined {
  const raw = text(value);
  const wrapped = raw.match(/^[\[(（【]\s*(.+?)\s*[\])）】]$/);
  const candidate = (wrapped?.[1] || raw).trim();
  return UNIT_TOKEN.test(candidate) ? candidate.replace(/^℃$/, '°C') : undefined;
}

function splitEmbeddedUnit(value: ImportCell): { name: string; unit?: string } {
  const raw = text(value);
  const match = raw.match(/^(.*?)\s+在\s+(%|s|ms|min|h|Pa|kPa|MPa|GPa|N|mN|μN|nm|μm|mm|cm|m|V|kV|A|mA|μA|Ω|kΩ|MΩ|°|°C|℃|K|Hz|kHz|MHz|GHz|μNm)$/i);
  if (match) return { name: match[1].trim(), unit: match[2] === '℃' ? '°C' : match[2] };
  const trailing = raw.match(/^(.*?)\s*[（(]\s*([^()（）]+)\s*[）)]\s*$/);
  if (!trailing) return { name: raw };
  const unit = parseUnitCell(trailing[2]);
  return unit ? { name: trailing[1].trim(), unit } : { name: raw };
}

function isDerivedLabel(value: ImportCell): boolean {
  return DERIVED_LABELS.has(normalized(value));
}

function parseMetadata(matrix: ImportCell[][], headerIndex: number): StructuredMetadataItem[] {
  const items: StructuredMetadataItem[] = [];
  for (let rowIndex = 0; rowIndex < headerIndex; rowIndex += 1) {
    for (const value of matrix[rowIndex]) {
      const raw = text(value);
      if (!raw || raw === '1') continue;
      for (const segment of raw.split(/[；;]/).map((part) => part.trim()).filter(Boolean)) {
        const match = segment.match(/^([^:：]+?)(?:\(([^)（）]+)\))?\s*[:：]\s*(.+)$/);
        if (!match) continue;
        items.push({
          sourceRow: rowIndex + 1,
          name: match[1].trim(),
          unit: match[2]?.trim(),
          value: match[3].trim(),
        });
      }
    }
  }
  return items;
}

function suggestedSeriesColumns(columns: StructuredColumn[], xColumnIndex: number): number[] {
  const candidates = columns
    .map((column, index) => ({ column, index }))
    .filter(({ index }) => index !== xColumnIndex);
  const raw = candidates.filter(({ column }) => (
    !DERIVED_COLUMN_KEYWORDS.some((keyword) => normalized(column.name).includes(normalized(keyword)))
  ));
  return (raw.length ? raw : candidates).map(({ index }) => index);
}

function findHeaderRow(matrix: ImportCell[][]): { index: number; unitIndex?: number } | null {
  let best: { index: number; unitIndex?: number; score: number } | null = null;
  const limit = Math.min(matrix.length, 30);
  for (let index = 0; index < limit; index += 1) {
    const row = matrix[index];
    const filledIndexes = row.map((value, column) => text(value) ? column : -1).filter((column) => column >= 0);
    if (filledIndexes.length < 2) continue;
    const textCells = filledIndexes.filter((column) => parseImportNumber(row[column]) === null).length;
    if (textCells / filledIndexes.length < 0.6) continue;

    const next = matrix[index + 1] || [];
    const unitCount = filledIndexes.filter((column) => parseUnitCell(next[column])).length;
    const unitIndex = unitCount >= Math.max(1, Math.floor(filledIndexes.length / 2)) ? index + 1 : undefined;
    const dataStart = unitIndex === undefined ? index + 1 : index + 2;
    const dataCandidates = matrix.slice(dataStart, Math.min(matrix.length, dataStart + 8));
    const numericRows = dataCandidates.filter((candidate) => numericRatio(candidate, filledIndexes) >= 0.6).length;
    if (numericRows === 0) continue;
    const score = filledIndexes.length * 2 + unitCount * 5 + numericRows * 3 - index;
    if (!best || score > best.score) best = { index, unitIndex, score };
  }
  return best ? { index: best.index, unitIndex: best.unitIndex } : null;
}

function chooseXColumn(columns: StructuredColumn[], rows: ImportCell[][]): number {
  let best = -1;
  let bestScore = -1;
  columns.forEach((column, index) => {
    const values = rows.map((row) => row[index]).filter((value) => text(value) !== '');
    if (!values.length || values.some((value) => parseImportNumber(value) === null)) return;
    const token = normalized(column.name);
    let score = index === 0 ? 2 : 0;
    if (/序号|编号|index|segment|segindex/.test(token)) score += 10;
    if (/^t$|时间|time/.test(token)) score += 6;
    const numbers = values.map((value) => parseImportNumber(value) as number);
    if (numbers.every((value, item) => item === 0 || value >= numbers[item - 1])) score += 3;
    if (score > bestScore) {
      best = index;
      bestScore = score;
    }
  });
  return best;
}

export function detectStructuredDataset(
  input: ImportCell[][],
  fallbackTitle: string,
): StructuredDatasetPreview | null {
  const width = input.reduce((maximum, row) => Math.max(maximum, row.length), 0);
  const matrix = input.map((row) => Array.from({ length: width }, (_, index) => row[index] ?? ''));
  const header = findHeaderRow(matrix);
  if (!header) return null;

  const headerValues = matrix[header.index];
  if (headerValues.some((value) => MATERIAL_NAME_HEADERS.has(normalized(value)))) return null;
  const activeColumns = headerValues
    .map((value, index) => text(value) || (index === 0 ? '测量序号' : '') ? index : -1)
    .filter((index) => index >= 0);
  if (activeColumns.length < 2) return null;

  const unitValues = header.unitIndex === undefined ? [] : matrix[header.unitIndex];
  const columns = activeColumns.map((sourceColumn, index) => {
    const embedded = splitEmbeddedUnit(headerValues[sourceColumn]);
    return {
      key: `series_${index + 1}`,
      name: embedded.name || (sourceColumn === 0 ? '测量序号' : `列${sourceColumn + 1}`),
      unit: parseUnitCell(unitValues[sourceColumn]) || embedded.unit,
      sourceColumn,
    };
  });

  const rows: ImportCell[][] = [];
  const sourceRows: number[] = [];
  const excludedRows: ExcludedStructuredRow[] = [];
  const start = (header.unitIndex ?? header.index) + 1;
  for (let index = start; index < matrix.length; index += 1) {
    const projected = columns.map((column) => matrix[index][column.sourceColumn]);
    const label = projected.find((value) => text(value) !== '') || '';
    if (isDerivedLabel(label)) {
      excludedRows.push({ sourceRow: index + 1, label: text(label), reason: 'derived_summary' });
      continue;
    }
    if (nonEmptyCount(projected) === 0) continue;
    const measurementColumns = projected.slice(1);
    if (numericRatio(measurementColumns) < 0.6) continue;
    rows.push(projected);
    sourceRows.push(index + 1);
  }
  if (rows.length === 0 || columns.length < 2) return null;

  const xColumnIndex = chooseXColumn(columns, rows);
  const metadata = parseMetadata(matrix, header.index);
  const warnings: string[] = [];
  if (xColumnIndex < 0) warnings.push('未找到全数值横坐标列，请在确认前选择或修正横坐标。');
  return {
    kind: 'measurement_dataset',
    title: fallbackTitle,
    headerRow: header.index + 1,
    unitRow: header.unitIndex === undefined ? undefined : header.unitIndex + 1,
    columns,
    rows,
    sourceRows,
    excludedRows,
    metadata,
    suggestedSeriesColumnIndexes: suggestedSeriesColumns(columns, xColumnIndex),
    xColumnIndex,
    warnings,
  };
}
