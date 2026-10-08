import assert from 'node:assert/strict';
import {
  buildHistogram,
  formatCompact,
  summarizeSeries,
} from '../.runtime/validation/utils/measurementVisualization.js';

const summary = summarizeSeries([1, 2, 3, 4]);
assert.ok(summary);
assert.equal(summary.count, 4);
assert.equal(summary.minimum, 1);
assert.equal(summary.maximum, 4);
assert.equal(summary.mean, 2.5);
assert.equal(summary.median, 2.5);
assert.equal(summary.first, 1);
assert.equal(summary.last, 4);
assert.equal(summarizeSeries([Number.NaN]), null);

const bins = buildHistogram([0, 1, 2, 3, 4], 2);
assert.equal(bins.length, 2);
assert.deepEqual(bins.map((bin) => bin.count), [2, 3]);
assert.equal(buildHistogram([5, 5, 5], 20)[0].count, 3);
assert.equal(buildHistogram([], 20).length, 0);
assert.equal(formatCompact(0.00001234), '1.234e-5');

console.log('measurement visualization tests passed');
