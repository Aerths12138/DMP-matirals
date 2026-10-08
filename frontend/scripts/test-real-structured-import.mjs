import assert from 'node:assert/strict';
import fs from 'node:fs';
import * as XLSX from 'xlsx';

import { detectAndDecode, parseWorkbookBuffer } from '../.runtime/validation/utils/fileParser.js';

// Regression fixture copied byte-for-byte from a GBK instrument CSV.
const fixture = 'veG5+7HtuPEgMQ0KLMCtyezOu9LG1Nq/ucCtx7+2yCzArcns06ax5CAozrvSxinU2r+5wK3Hv7bILMCtyezTpsGm1Nq/ucCtx7+2yCzBptTav7nArce/tsgsyrG85NTav7nArce/tsgszrvSxtTav7nArce/tsgNCiwobW0pLCglKSwoTVBhKSwoTiksKHMpLChtbSkNCiIxIiwiMTcxLjMxIiwiNTcwLjkwIiwiMTUuMDUiLCI1Ni4yMiIsIjUxLjQzIiwiMTcxLjMyIg0KIjIiLCIxNjkuNTEiLCI1NjQuOTkiLCIxNS4yNyIsIjU3LjA0IiwiNTAuODkiLCIxNjkuNTEiDQoiseTS7M+1yv0iLCIwLjc1IiwiMC43NCIsIjEuMDIiLCIxLjAyIiwiMC43NSIsIjAuNzUiDQoiserXvLe9su4iLCIxLjI4IiwiNC4xOCIsIjAuMTUiLCIwLjU4IiwiMC4zOCIsIjEuMjgiDQoi1+6089a1IiwiMTcxLjMxIiwiNTcwLjkwIiwiMTUuMjciLCI1Ny4wNCIsIjUxLjQzIiwiMTcxLjMyIg0KItfu0KHWtSIsIjE2OS41MSIsIjU2NC45OSIsIjE1LjA1IiwiNTYuMjIiLCI1MC44OSIsIjE2OS41MSINCiLGvb751rUiLCIxNzAuNDEiLCI1NjcuOTQiLCIxNS4xNiIsIjU2LjYzIiwiNTEuMTYiLCIxNzAuNDIiDQoNCr3hufux7bjxIDINCg0KDQo=';
const bytes = Buffer.from(fixture, 'base64');
const arrayBuffer = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
const text = detectAndDecode(arrayBuffer);
assert.match(text, /结果表格 1/);
assert.match(text, /拉伸应力在抗拉强度/);

const workbook = XLSX.read(text, { type: 'string', raw: true });
const sheet = workbook.Sheets[workbook.SheetNames[0]];
const matrix = XLSX.utils.sheet_to_json(sheet, { header: 1, defval: '', blankrows: false });
const { detectStructuredDataset } = await import('../.runtime/validation/utils/structuredImport.js');
const result = detectStructuredDataset(matrix, '1-1_1');
assert.ok(result);
assert.equal(result.title, '1-1_1');
assert.equal(result.rows.length, 2);
assert.equal(result.columns.length, 7);
assert.equal(result.columns[3].unit, 'MPa');
assert.equal(result.excludedRows.length, 5);
assert.equal(result.xColumnIndex, 0);
console.log(JSON.stringify({
  title: result.title,
  points: result.rows.length,
  columns: result.columns.map(({ name, unit }) => ({ name, unit })),
  excluded: result.excludedRows.map(({ label, sourceRow }) => ({ label, sourceRow })),
  xColumn: result.columns[result.xColumnIndex],
}, null, 2));

const conductivityPath = process.env.CONDUCTIVITY_WORKBOOK;
if (conductivityPath && fs.existsSync(conductivityPath)) {
  const source = fs.readFileSync(conductivityPath);
  const buffer = source.buffer.slice(source.byteOffset, source.byteOffset + source.byteLength);
  const conductivity = parseWorkbookBuffer(buffer, '原始.xlsx').structuredDataset;
  assert.ok(conductivity);
  assert.equal(conductivity.headerRow, 19);
  assert.equal(conductivity.rows.length, 1195);
  assert.equal(conductivity.xColumnIndex, 0);
  assert.deepEqual(conductivity.suggestedSeriesColumnIndexes, [1]);
  assert.ok(conductivity.metadata.some((item) => item.name === '样品厚度' && item.value === '204'));
  console.log(JSON.stringify({
    conductivityPoints: conductivity.rows.length,
    metadataItems: conductivity.metadata.length,
    keptSeries: conductivity.suggestedSeriesColumnIndexes.map((index) => conductivity.columns[index].name),
  }, null, 2));
}
