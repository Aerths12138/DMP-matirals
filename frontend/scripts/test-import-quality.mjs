import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import * as XLSX from 'xlsx';

import {
  analyzeImportQuality,
  summarizeImportQuality,
} from '../.runtime/validation/utils/importQuality.js';
import {
  createCorrectedImportWorkbook,
  importQualityReportFilename,
} from '../.runtime/validation/utils/importCorrectedExport.js';

const fixtureDirectory = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '../../demo/import-quality',
);
const standardMapping = {
  名称: 'name',
  材料类型: 'material_type',
  拉伸强度: 'property',
  电导率: 'result',
  批次说明: 'property',
};
let assertionCount = 0;

function equal(actual, expected, message) {
  assertionCount += 1;
  assert.equal(actual, expected, message);
}

function deepEqual(actual, expected, message) {
  assertionCount += 1;
  assert.deepEqual(actual, expected, message);
}

function loadFixture(filename) {
  const csv = readFileSync(path.join(fixtureDirectory, filename), 'utf8');
  const workbook = XLSX.read(csv, { type: 'string', raw: true });
  const matrix = XLSX.utils.sheet_to_json(workbook.Sheets[workbook.SheetNames[0]], {
    header: 1,
    defval: '',
    blankrows: false,
    raw: false,
  });
  return {
    headers: matrix[0].map((value) => String(value).trim()),
    rows: matrix.slice(1).map((row) => row.map((value) => String(value).trim())),
  };
}

function issuesFor(filename, mapping = standardMapping) {
  const fixture = loadFixture(filename);
  return {
    ...fixture,
    issues: analyzeImportQuality(fixture.headers, fixture.rows, mapping),
  };
}

const clean = issuesFor('01_clean_scientific.csv');
equal(clean.issues.length, 0, 'clean scientific notation fixture passes');
equal(summarizeImportQuality(clean.issues).blockingCount, 0, 'clean fixture is importable');
console.log('[PASS] 01 clean scientific notation');

const emptyName = issuesFor('02_empty_material_name.csv');
equal(emptyName.issues.length, 1, 'empty-name fixture reports one issue');
deepEqual(
  { code: emptyName.issues[0].code, severity: emptyName.issues[0].severity, sourceRow: emptyName.issues[0].sourceRow },
  { code: 'empty_material_name', severity: 'error', sourceRow: 3 },
  'empty material name is a row-addressed blocking error',
);
equal(summarizeImportQuality(emptyName.issues).blockingCount, 1, 'empty name blocks import');
console.log('[PASS] 02 empty material name is blocked');

const duplicates = issuesFor('03_duplicate_names.csv');
deepEqual(duplicates.issues.map((issue) => issue.code), [
  'duplicate_material_name',
  'duplicate_material_name',
], 'normalized duplicates are both detected');
deepEqual(duplicates.issues.map((issue) => issue.sourceRow), [3, 4], 'duplicate source rows are preserved');
deepEqual(duplicates.issues.map((issue) => issue.relatedSourceRow), [2, 2], 'duplicates point to the first occurrence');
equal(summarizeImportQuality(duplicates.issues).blockingCount, 0, 'duplicates warn without blocking');
console.log('[PASS] 03 normalized duplicate names warn');

const mixed = issuesFor('04_mixed_numeric_text.csv');
equal(mixed.issues.length, 1, 'mixed numeric/text fixture reports one issue');
deepEqual(
  { code: mixed.issues[0].code, severity: mixed.issues[0].severity, sourceRow: mixed.issues[0].sourceRow, column: mixed.issues[0].column },
  { code: 'mixed_numeric_text', severity: 'warning', sourceRow: 3, column: '拉伸强度' },
  'mixed values identify the exact source row and column',
);
console.log('[PASS] 04 mixed numeric and text values warn');

const shortRows = issuesFor('05_short_rows.csv');
equal(shortRows.issues.length, 0, 'short rows with a material name remain valid');
console.log('[PASS] 05 short rows remain importable');

const allText = issuesFor('06_all_text_property.csv');
equal(allText.issues.length, 0, 'an all-text property column is not treated as mixed data');
console.log('[PASS] 06 all-text property avoids a false positive');

const combined = issuesFor('07_combined_issues.csv');
deepEqual(combined.issues.map((issue) => issue.code), [
  'empty_material_name',
  'duplicate_material_name',
  'mixed_numeric_text',
], 'combined fixture exposes all deterministic issue types');
deepEqual(summarizeImportQuality(combined.issues), {
  blockingCount: 1,
  warningCount: 2,
  issueCount: 3,
}, 'combined summary separates blockers from warnings');
console.log('[PASS] 07 combined issues produce a complete summary');

const numericFormats = issuesFor('08_numeric_formats.csv');
equal(numericFormats.issues.length, 0, 'supported numeric text formats are not flagged');
console.log('[PASS] 08 supported numeric formats pass');

const missingMapping = issuesFor('09_missing_name_mapping.csv', { 拉伸强度: 'property' });
equal(missingMapping.issues.length, 1, 'missing name mapping reports one issue');
deepEqual(
  { code: missingMapping.issues[0].code, severity: missingMapping.issues[0].severity },
  { code: 'missing_name_mapping', severity: 'error' },
  'missing material-name mapping blocks import',
);
console.log('[PASS] 09 missing material-name mapping is blocked');

const reportWorkbook = createCorrectedImportWorkbook(
  combined.headers,
  combined.rows,
  standardMapping,
  combined.issues,
);
deepEqual(reportWorkbook.SheetNames, ['Corrected Data', 'Field Mapping', 'Quality Report'], 'report workbook remains reviewable');
const reportRows = XLSX.utils.sheet_to_json(reportWorkbook.Sheets['Quality Report'], {
  header: 1,
  defval: '',
  raw: true,
});
equal(reportRows.length, 4, 'quality report contains a header plus all combined issues');
deepEqual(reportRows.slice(1).map((row) => row[0]), [3, 4, 3], 'quality report preserves source rows');
equal(importQualityReportFilename('07:combined?.csv'), '07_combined__quality_report.xlsx', 'report filenames are safe on Windows');
console.log('[PASS] quality report export contains every issue');

console.log(`Import quality fixtures: ${assertionCount} assertions passed across 9 demo files`);
