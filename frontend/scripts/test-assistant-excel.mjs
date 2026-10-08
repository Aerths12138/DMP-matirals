import assert from 'node:assert/strict';
import * as XLSX from 'xlsx';

import {
  MAX_ASSISTANT_EXCEL_BYTES,
  DEFAULT_ASSISTANT_EXCEL_PROMPT,
  buildAssistantUserContent,
  canSendAssistantRequest,
  createAssistantFileState,
  failAssistantFileSend,
  readAssistantExcelSheetNames,
  removeAssistantExcelFile,
  selectAssistantExcelFile,
  startAssistantFileSend,
  succeedAssistantFileSend,
  validateAssistantExcelFile,
} from '../.runtime/validation/pages/Assistant/assistantFileState.js';
import {
  canConfirmAssistantImport,
  clearAssistantImport,
  confirmAssistantImport,
  createAssistantImportState,
  failAssistantImport,
  receiveAssistantImportPreview,
  startAssistantImport,
} from '../.runtime/validation/pages/Assistant/assistantImportState.js';

const workbook = {
  name: 'material-data.xlsx',
  size: MAX_ASSISTANT_EXCEL_BYTES,
  secretCell: 'do not put workbook contents in history',
};

assert.equal(validateAssistantExcelFile(workbook), null, 'a .xlsx file at 5 MiB is accepted');
assert.match(
  validateAssistantExcelFile({ name: 'material-data.xls', size: 1024 }),
  /\.xlsx/,
  'legacy .xls files are rejected',
);
assert.match(
  validateAssistantExcelFile({ name: 'material-data.xlsx', size: MAX_ASSISTANT_EXCEL_BYTES + 1 }),
  /5 MiB/,
  'files wider than the size boundary are rejected',
);

const empty = createAssistantFileState();
assert.equal(canSendAssistantRequest('', empty), false, 'an empty message without a file cannot send');
assert.equal(canSendAssistantRequest('查询材料', empty), true, 'text can send without a file');

const selected = selectAssistantExcelFile(empty, workbook);
assert.equal(selected.file, workbook, 'selection retains the browser File object');
assert.equal(selected.phase, 'selected', 'a valid workbook becomes selected');
assert.equal(canSendAssistantRequest('', selected), true, 'a workbook can send without typed text');
assert.equal(
  buildAssistantUserContent('', selected.file),
  `${DEFAULT_ASSISTANT_EXCEL_PROMPT}\n[Excel：material-data.xlsx]`,
  'an attachment-only request receives the default summary prompt',
);
assert.equal(
  buildAssistantUserContent('  分析异常值  ', selected.file),
  '分析异常值\n[Excel：material-data.xlsx]',
  'typed prompts are trimmed and retain only the attachment filename',
);

const invalidSelection = selectAssistantExcelFile(selected, { name: 'notes.pdf', size: 20 });
assert.equal(invalidSelection.file, workbook, 'an invalid selection does not replace the current workbook');
assert.match(invalidSelection.error, /\.xlsx/, 'an invalid selection exposes a useful error');

const sending = startAssistantFileSend(selected);
assert.equal(sending.phase, 'sending', 'send start enters the sending phase');
assert.equal(canSendAssistantRequest('重复发送', sending), false, 'sending prevents duplicate requests');

const succeeded = succeedAssistantFileSend(sending);
assert.equal(succeeded.phase, 'success', 'successful reads are recorded');
assert.equal(succeeded.file, workbook, 'success keeps the workbook for a follow-up question');

const failed = failAssistantFileSend(sending, '解析失败');
assert.equal(failed.phase, 'failure', 'failed reads are recorded');
assert.equal(failed.file, workbook, 'failure keeps the workbook for retry');
assert.equal(failed.error, '解析失败', 'failure exposes its error');

const history = buildAssistantUserContent('', {
  name: 'C:\\fakepath\\material-data.xlsx',
  size: 123,
  secretCell: 'private measurement',
});
assert.equal(
  history,
  `${DEFAULT_ASSISTANT_EXCEL_PROMPT}\n[Excel：material-data.xlsx]`,
  'history displays the prompt and only the workbook filename',
);
assert.equal(history.includes('private measurement'), false, 'history does not contain workbook values');
assert.equal(history.includes('123'), false, 'history does not contain file metadata');

const generatedWorkbook = XLSX.utils.book_new();
XLSX.utils.book_append_sheet(
  generatedWorkbook,
  XLSX.utils.aoa_to_sheet([['材料名称'], ['首表材料']]),
  '原始数据',
);
XLSX.utils.book_append_sheet(
  generatedWorkbook,
  XLSX.utils.aoa_to_sheet([['材料名称'], ['目标材料']]),
  '待导入数据',
);
const generatedBytes = XLSX.write(generatedWorkbook, { type: 'array', bookType: 'xlsx' });
const generatedFile = {
  arrayBuffer: async () => generatedBytes,
};
const sheetNames = await readAssistantExcelSheetNames(generatedFile);
assert.deepEqual(
  sheetNames,
  ['原始数据', '待导入数据'],
  'worksheet names retain workbook order for user selection',
);
assert.equal(sheetNames[0], '原始数据', 'the first worksheet is the default selection');
assert.equal(sheetNames[1], '待导入数据', 'a later worksheet can be selected for import');

const removed = removeAssistantExcelFile();
assert.deepEqual(removed, empty, 'explicit removal clears the workbook and status');

const importPreview = {
  blocking_errors: [],
  import_rows: [{ name: 'Sample A', properties: { dielectric_constant: 3.2 } }],
};
let importCalls = 0;
const emptyImport = createAssistantImportState();
assert.equal(canConfirmAssistantImport(emptyImport), false, 'import is unavailable without a preview');

const readyImport = receiveAssistantImportPreview(importPreview);
assert.equal(readyImport.phase, 'ready', 'a formatted workbook becomes ready for review');
assert.equal(canConfirmAssistantImport(readyImport), true, 'a valid preview can be confirmed');
assert.equal(importCalls, 0, 'receiving a formatted preview never writes data');

const blockedImport = receiveAssistantImportPreview({
  blocking_errors: ['缺少材料名称列'],
  import_rows: importPreview.import_rows,
});
assert.equal(canConfirmAssistantImport(blockedImport), false, 'blocking format errors prevent import');
assert.equal(
  await confirmAssistantImport(blockedImport, async () => { importCalls += 1; }),
  null,
  'a blocked preview cannot invoke the importer',
);
assert.equal(importCalls, 0, 'data remains untouched before explicit confirmation');

const importing = startAssistantImport(readyImport);
assert.equal(importing.phase, 'importing', 'explicit confirmation enters the importing phase');
const importResult = await confirmAssistantImport(readyImport, async (rows) => {
  importCalls += 1;
  assert.equal(rows, importPreview.import_rows, 'confirmation submits the reviewed rows');
  return { total: rows.length, created: rows.length, failed: 0 };
});
assert.deepEqual(importResult, { total: 1, created: 1, failed: 0 });
assert.equal(importCalls, 1, 'explicit confirmation invokes the importer exactly once');

const failedImport = failAssistantImport(importing, '导入失败');
assert.equal(failedImport.preview, importPreview, 'an import failure retains the preview for retry');
assert.equal(failedImport.error, '导入失败', 'an import failure remains visible');
assert.equal(canConfirmAssistantImport(failedImport), true, 'a failed import can be confirmed again');
assert.deepEqual(clearAssistantImport(), emptyImport, 'removing or replacing a file clears its preview');

console.log('AI assistant Excel and confirmed import state checks passed');
