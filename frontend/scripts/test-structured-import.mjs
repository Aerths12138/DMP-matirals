import assert from 'node:assert/strict';
import { detectStructuredDataset } from '../.runtime/validation/utils/structuredImport.js';

const tensile = [
  ['结果表格 1', '', '', ''],
  ['', '拉伸位移在抗拉强度', '拉伸应变在抗拉强度', '拉伸应力在抗拉强度'],
  ['', '(mm)', '(%)', '(MPa)'],
  ['1', '171.31', '570.90', '15.05'],
  ['2', '169.51', '564.99', '15.27'],
  ['变异系数', '0.75', '0.74', '1.02'],
  ['平均值', '170.41', '567.94', '15.16'],
  ['', '', '', ''],
  ['结果表格 2', '', '', ''],
];
const result = detectStructuredDataset(tensile, '1-1_1');
assert.ok(result);
assert.equal(result.headerRow, 2);
assert.equal(result.unitRow, 3);
assert.equal(result.rows.length, 2);
assert.deepEqual(result.sourceRows, [4, 5]);
assert.deepEqual(result.excludedRows.map((row) => row.label), ['变异系数', '平均值']);
assert.equal(result.columns[1].unit, 'mm');
assert.equal(result.xColumnIndex, 0);
assert.deepEqual(result.suggestedSeriesColumnIndexes, [1, 2, 3]);

const series = [
  ['SegIndex', 't 在 s', "G' 在 Pa", 'T 在 °C'],
  ['1|1', '7.3', '11738', '134.4'],
  ['1|2', '10.3', '10795', '134.0'],
];
const seriesResult = detectStructuredDataset(series, 'series');
assert.ok(seriesResult);
assert.equal(seriesResult.xColumnIndex, 1);
assert.equal(seriesResult.columns[1].name, 't');
assert.equal(seriesResult.columns[1].unit, 's');

const materialList = [
  ['材料名称', '材料类型', '密度'],
  ['A', 'polymer', '1.2'],
];
assert.equal(detectStructuredDataset(materialList, 'materials'), null);

const conductivity = [
  ['高场电导测试', '', '', '', '', ''],
  ['测试项目：极化测试', '', '', '', '', ''],
  ['极化电场(kV/mm)：5', '样品厚度(μm)：204', '测试温度(℃)：28', '', '', ''],
  ['测试数据:', '', '', '', '', ''],
  ['时间t(s)', '极化电流I(pA)', '电流密度J(A/m2)', 'U/I(GΩ)', '电阻率ρ(Ω.m)', '电导率σ(Ｓ/m)'],
  ['0', '1.4', '1.23787E-8', '7.28571E+5', '4.03919E+14', '2.47574E-15'],
  ['1', '2.3', '2.03365E-8', '4.43478E+5', '2.45864E+14', '4.06729E-15'],
];
const conductivityResult = detectStructuredDataset(conductivity, '原始');
assert.ok(conductivityResult);
assert.equal(conductivityResult.rows.length, 2);
assert.equal(conductivityResult.xColumnIndex, 0);
assert.deepEqual(conductivityResult.suggestedSeriesColumnIndexes, [1]);
assert.deepEqual(
  conductivityResult.metadata.map(({ name, value, unit }) => ({ name, value, unit })),
  [
    { name: '测试项目', value: '极化测试', unit: undefined },
    { name: '极化电场', value: '5', unit: 'kV/mm' },
    { name: '样品厚度', value: '204', unit: 'μm' },
    { name: '测试温度', value: '28', unit: '℃' },
  ],
);

console.log('structured import tests passed');
