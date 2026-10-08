export interface SeriesStatistics {
  count: number;
  minimum: number;
  maximum: number;
  mean: number;
  median: number;
  standardDeviation: number;
  first: number;
  last: number;
}

export interface HistogramBin {
  label: string;
  start: number;
  end: number;
  count: number;
}

export function summarizeSeries(values: number[]): SeriesStatistics | null {
  const valid = values.filter(Number.isFinite);
  if (valid.length === 0) return null;
  const sorted = [...valid].sort((left, right) => left - right);
  const sum = valid.reduce((total, value) => total + value, 0);
  const mean = sum / valid.length;
  const middle = Math.floor(sorted.length / 2);
  const median = sorted.length % 2
    ? sorted[middle]
    : (sorted[middle - 1] + sorted[middle]) / 2;
  const variance = valid.reduce((total, value) => total + (value - mean) ** 2, 0) / valid.length;
  return {
    count: valid.length,
    minimum: sorted[0],
    maximum: sorted[sorted.length - 1],
    mean,
    median,
    standardDeviation: Math.sqrt(variance),
    first: valid[0],
    last: valid[valid.length - 1],
  };
}

export function buildHistogram(values: number[], requestedBinCount = 20): HistogramBin[] {
  const valid = values.filter(Number.isFinite);
  if (valid.length === 0) return [];
  const minimum = Math.min(...valid);
  const maximum = Math.max(...valid);
  if (minimum === maximum) {
    return [{ label: formatRange(minimum, maximum), start: minimum, end: maximum, count: valid.length }];
  }
  const binCount = Math.max(1, Math.min(Math.floor(requestedBinCount), valid.length));
  const width = (maximum - minimum) / binCount;
  const bins = Array.from({ length: binCount }, (_, index) => {
    const start = minimum + index * width;
    const end = index === binCount - 1 ? maximum : minimum + (index + 1) * width;
    return { label: formatRange(start, end), start, end, count: 0 };
  });
  valid.forEach((value) => {
    const index = value === maximum ? binCount - 1 : Math.floor((value - minimum) / width);
    bins[index].count += 1;
  });
  return bins;
}

function formatRange(start: number, end: number): string {
  return `${formatCompact(start)}–${formatCompact(end)}`;
}

export function formatCompact(value: number): string {
  if (value === 0) return '0';
  const absolute = Math.abs(value);
  return absolute >= 10000 || absolute < 0.001
    ? value.toExponential(3)
    : Number(value.toPrecision(5)).toString();
}
