import assert from 'node:assert/strict';

import {
  applyImportAlignmentFailure,
  applyImportAlignmentSuccess,
  confirmImport,
} from '../.runtime/validation/utils/importAlignmentFlow.js';
import {
  correctedImportFilename,
  createCorrectedImportWorkbook,
  importQualityReportFilename,
} from '../.runtime/validation/utils/importCorrectedExport.js';
import {
  analyzeImportQuality,
  summarizeImportQuality,
} from '../.runtime/validation/utils/importQuality.js';
import * as XLSX from 'xlsx';

const originalRows = [['Sample A', '1.2E-3']];
const originalMapping = { material: 'name', strength: 'property' };
const initialState = {
  rows: originalRows,
  columnMapping: originalMapping,
  alignmentResult: null,
  alignmentError: null,
};
let importCalls = 0;

const alignmentResult = {
  mapping: { material: 'name', strength: 'result' },
  normalized_rows: [['Sample A', 0.0012]],
  conversion_count: 1,
  conversions: [],
  warnings: [],
};
const aligned = applyImportAlignmentSuccess(initialState, alignmentResult);
assert.deepEqual(aligned.columnMapping, alignmentResult.mapping, 'success updates column mapping');
assert.deepEqual(aligned.rows, alignmentResult.normalized_rows, 'success updates preview rows');
assert.equal(aligned.alignmentResult, alignmentResult, 'success exposes the alignment preview result');
assert.equal(aligned.alignmentError, null, 'success clears a previous error');
assert.equal(importCalls, 0, 'successful alignment does not import before confirmation');

const failed = applyImportAlignmentFailure(initialState, '表头不匹配');
assert.equal(failed.rows, originalRows, 'failure preserves original preview rows');
assert.equal(failed.columnMapping, originalMapping, 'failure preserves original mapping');
assert.equal(failed.alignmentResult, null, 'failure clears a stale success result');
assert.equal(failed.alignmentError, '表头不匹配', 'failure exposes the error message');
assert.equal(importCalls, 0, 'failed alignment does not import before confirmation');

confirmImport(() => { importCalls += 1; });
assert.equal(importCalls, 1, 'explicit confirmation triggers the actual import once');

const missingMappingIssues = analyzeImportQuality(
  ['strength'],
  [['1.2']],
  { strength: 'property' },
);
assert.equal(missingMappingIssues[0].code, 'missing_name_mapping');

const qualityIssues = analyzeImportQuality(
  ['material', 'strength'],
  [
    ['Sample A', '1.2E-3'],
    ['', '2.5'],
    [' sample a ', 'not measured'],
  ],
  originalMapping,
);
const emptyNameIssue = qualityIssues.find((issue) => issue.code === 'empty_material_name');
assert.equal(emptyNameIssue?.sourceRow, 3, 'empty names report the source spreadsheet row');
assert.equal(summarizeImportQuality(qualityIssues).blockingCount, 1, 'empty names block import');
const duplicateIssue = qualityIssues.find((issue) => issue.code === 'duplicate_material_name');
assert.equal(duplicateIssue?.sourceRow, 4, 'normalized duplicate names report the later source row');
assert.equal(duplicateIssue?.relatedSourceRow, 2, 'duplicates point to the first source row');
const mixedIssue = qualityIssues.find((issue) => issue.code === 'mixed_numeric_text');
assert.equal(mixedIssue?.sourceRow, 4, 'mixed numeric/text warnings identify the source row');
assert.equal(mixedIssue?.column, 'strength', 'mixed numeric/text warnings identify the column');

const validIssues = analyzeImportQuality(
  ['material', 'strength'],
  [['Sample A', '1.2'], ['Sample B']],
  originalMapping,
);
assert.equal(summarizeImportQuality(validIssues).blockingCount, 0, 'valid and short rows remain importable');
assert.equal(confirmImport(() => { importCalls += 1; }, false), false, 'quality errors prevent confirmation');
assert.equal(importCalls, 1, 'blocked confirmation does not call the import callback');
assert.equal(confirmImport(() => { importCalls += 1; }, true), true, 'quality-approved confirmation proceeds');
assert.equal(importCalls, 2, 'approved confirmation calls the import callback once');

const workbook = createCorrectedImportWorkbook(
  ['material', 'strength'],
  aligned.rows,
  aligned.columnMapping,
  qualityIssues,
);
assert.deepEqual(workbook.SheetNames, ['Corrected Data', 'Field Mapping', 'Quality Report']);
const exportedRows = XLSX.utils.sheet_to_json(workbook.Sheets['Corrected Data'], {
  header: 1,
  defval: '',
  raw: true,
});
assert.deepEqual(exportedRows, [
  ['material', 'strength'],
  ['Sample A', 0.0012],
], 'download workbook contains the aligned preview values');
assert.equal(typeof exportedRows[1][1], 'number', 'normalized scientific notation remains numeric');
const exportedMapping = XLSX.utils.sheet_to_json(workbook.Sheets['Field Mapping'], {
  header: 1,
  defval: '',
  raw: true,
});
assert.deepEqual(exportedMapping, [
  ['Source column', 'System field'],
  ['material', 'name'],
  ['strength', 'result'],
]);
const exportedQuality = XLSX.utils.sheet_to_json(workbook.Sheets['Quality Report'], {
  header: 1,
  defval: '',
  raw: true,
});
assert.deepEqual(exportedQuality[0], [
  'Source row', 'Severity', 'Code', 'Column', 'Related source row', 'Message',
]);
assert.equal(exportedQuality.length, qualityIssues.length + 1, 'quality report exports every issue');
assert.equal(correctedImportFilename('measurements.csv'), 'measurements_corrected.xlsx');
assert.equal(correctedImportFilename(undefined), 'data_corrected.xlsx');
assert.equal(importQualityReportFilename('measurements.csv'), 'measurements_quality_report.xlsx');

console.log('Import alignment and quality flow: 32 assertions passed');
