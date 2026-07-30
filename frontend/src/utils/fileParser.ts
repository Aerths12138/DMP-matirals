/**
 * File parser for CSV and Excel (.xlsx/.xls) files using SheetJS.
 * Handles encoding auto-detection for Chinese CSV files (UTF-8 / GBK).
 */

import * as XLSX from 'xlsx';

export interface CsvData {
  headers: string[];
  rows: string[][];
}

/**
 * Parse CSV or Excel (.xlsx/.xls) file into headers + data rows.
 *
 * For .xlsx/.xls: uses SheetJS directly (Excel stores strings internally).
 * For .csv: auto-detects encoding (UTF-8 / GBK) before parsing.
 */
export function parseFile(file: File): Promise<CsvData> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    const isCsv = file.name.toLowerCase().endsWith('.csv');

    reader.onload = (e) => {
      try {
        const buffer = e.target!.result as ArrayBuffer;

        if (isCsv) {
          // Auto-detect encoding for CSV
          const text = detectAndDecode(buffer);
          const workbook = XLSX.read(text, { type: 'string', raw: true });
          resolve(extractData(workbook));
        } else {
          // Excel files: SheetJS handles encoding internally
          const data = new Uint8Array(buffer);
          const workbook = XLSX.read(data, { type: 'array' });
          resolve(extractData(workbook));
        }
      } catch (err) {
        reject(err);
      }
    };

    reader.onerror = () => reject(new Error('文件读取失败，请重试'));
    reader.readAsArrayBuffer(file);
  });
}

/**
 * Try to decode a byte buffer as text.
 * Attempts UTF-8 first; falls back to GBK if high bytes are present
 * and the UTF-8 result contains unexpected characters.
 */
function detectAndDecode(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);

  // Strip BOM if present (UTF-8 BOM: EF BB BF)
  let start = 0;
  if (bytes.length >= 3 && bytes[0] === 0xef && bytes[1] === 0xbb && bytes[2] === 0xbf) {
    start = 3;
  }

  const hasHighBytes = bytes.slice(start).some((b) => b >= 0x80);

  if (!hasHighBytes) {
    // Pure ASCII — just use UTF-8
    return new TextDecoder('utf-8').decode(bytes.slice(start));
  }

  // Try UTF-8 first
  const utf8Text = new TextDecoder('utf-8', { fatal: false }).decode(bytes.slice(start));

  // Check if UTF-8 result looks valid (low replacement char ratio)
  const replacementCount = (utf8Text.match(/�/g) || []).length;
  const totalChars = utf8Text.length;

  if (totalChars > 0 && replacementCount / totalChars < 0.05) {
    // UTF-8 looks good
    return utf8Text;
  }

  // UTF-8 had many replacement chars — try GBK
  try {
    const gbkText = new TextDecoder('gbk', { fatal: false }).decode(bytes.slice(start));
    const gbkReplacement = (gbkText.match(/�/g) || []).length;

    // Use whichever has fewer replacement characters
    if (gbkReplacement < replacementCount) {
      return gbkText;
    }
  } catch {
    // GBK decoder not available (e.g., Firefox) — keep UTF-8 result
  }

  return utf8Text;
}

/**
 * Deduplicate repeated header names by appending _2, _3, etc.
 * First occurrence keeps original name (no suffix).
 * e.g. ["温度", "电压", "温度", "温度"] → ["温度", "电压", "温度_2", "温度_3"]
 */
function deduplicateHeaders(headers: string[]): string[] {
  const seen = new Map<string, number>();
  return headers.map((h) => {
    const count = seen.get(h) || 0;
    seen.set(h, count + 1);
    if (count === 0) return h;
    return `${h}_${count + 1}`;
  });
}

function extractData(workbook: XLSX.WorkBook): CsvData {
  const firstSheet = workbook.SheetNames[0];
  if (!firstSheet) {
    return { headers: [], rows: [] };
  }

  const sheet = workbook.Sheets[firstSheet];

  // Convert to array-of-arrays
  const aoa: any[][] = XLSX.utils.sheet_to_json(sheet, {
    header: 1,
    defval: '',
    blankrows: false,
  });

  if (aoa.length === 0) {
    return { headers: [], rows: [] };
  }

  const headers = aoa[0].map((h) => String(h ?? '').trim());
  // Replace empty headers with placeholder names, then deduplicate
  const rawHeaders = headers.map((h, i) => h || `列${i + 1}`);
  const cleanHeaders = deduplicateHeaders(rawHeaders);

  const rows = aoa.slice(1).map((row) =>
    cleanHeaders.map((_, i) => {
      const v = row[i];
      return v != null ? String(v).trim() : '';
    })
  );

  // Filter completely empty rows
  const nonEmptyRows = rows.filter((r) => r.some((v) => v !== ''));

  return { headers: cleanHeaders, rows: nonEmptyRows };
}

/**
 * Map column headers to known material fields.
 * Supports both Chinese and English column names.
 */
export function autoMapColumns(headers: string[]): Record<string, string> {
  const KNOWN_FIELDS: Record<string, string> = {
    '名称': 'name', '材料名称': 'name', '样品名称': 'name',
    'name': 'name', 'material': 'name',
    '类型': 'material_type', '材料类型': 'material_type', '分类': 'material_type',
    'type': 'material_type', 'material_type': 'material_type',
    '化学式': 'formula_string', '分子式': 'formula_string',
    'formula': 'formula_string', 'formula_string': 'formula_string',
    'hill公式': 'hill_formula', 'hill_formula': 'hill_formula',
    '别名': 'aliases', 'aliases': 'aliases',
    '描述': 'description', '说明': 'description',
    'description': 'description',
    '备注': 'notes', 'notes': 'notes',
    '测试名称': 'test_name', '实验名称': 'test_name', 'test_name': 'test_name',
    '测试方法': 'test_method', '试验方法': 'test_method', 'test_method': 'test_method',
  };

  // Keywords that suggest a column is a test condition (not a measurement)
  const CONDITION_KEYWORDS = [
    '温度', '温度(°c)', '温度(℃)', 'temperature', 'temp', 't',
    '频率', 'frequency', 'freq',
    '湿度', 'humidity', 'rh',
    '时间', 'time', 'duration',
    '压力', 'pressure', '压强',
    '电压', 'voltage',
    '电流', 'current',
    'ph', 'ph值',
    '浓度', 'concentration',
    '气氛', 'atmosphere',
    '升温速率', 'heating_rate', '升温速度',
    '保温时间', 'holding_time',
    '应变率', 'strain_rate',
    '载荷', 'load',
  ];

  const mapping: Record<string, string> = {};

  // Helper: strip dedup suffix like "_2", "_3" for matching
  const baseName = (h: string) => h.replace(/_\d+$/, '').trim();

  for (const h of headers) {
    const key = h.trim().toLowerCase();
    const base = baseName(key);

    if (KNOWN_FIELDS[key] || KNOWN_FIELDS[base]) {
      mapping[h] = KNOWN_FIELDS[key] || KNOWN_FIELDS[base];
    } else if (CONDITION_KEYWORDS.some((kw) => base.includes(kw))) {
      mapping[h] = 'condition';
    } else {
      mapping[h] = 'result';
    }
  }
  return mapping;
}
