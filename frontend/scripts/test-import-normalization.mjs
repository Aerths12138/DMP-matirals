import assert from 'node:assert/strict';

import {
  cleanImportCell,
  parseImportNumber,
} from '../.runtime/validation/importNormalization.js';

assert.equal(parseImportNumber('1.23E-4'), 0.000123);
assert.equal(parseImportNumber('3\u00d710\u207b\u00b3'), 0.003);
assert.ok(Math.abs(parseImportNumber('1.2 x 10^-5') - 0.000012) < 1e-15);
assert.equal(parseImportNumber('1,234.5'), 1234.5);
assert.equal(parseImportNumber('\uff11\uff0e\uff15\uff25\uff0d\uff12'), 0.015);
assert.equal(parseImportNumber('1.2 MPa'), null);
assert.equal(parseImportNumber('NaN'), null);
assert.equal(parseImportNumber('C10H8'), null);
assert.equal(cleanImportCell(0.003), '0.003');
assert.equal(cleanImportCell('  sample A  '), 'sample A');

console.log('Import normalization: 10 assertions passed');
