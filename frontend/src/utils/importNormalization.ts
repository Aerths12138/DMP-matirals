export type ImportCell = string | number;

const superscriptDigits: Record<string, string> = {
  '\u2070': '0',
  '\u00b9': '1',
  '\u00b2': '2',
  '\u00b3': '3',
  '\u2074': '4',
  '\u2075': '5',
  '\u2076': '6',
  '\u2077': '7',
  '\u2078': '8',
  '\u2079': '9',
  '\u207a': '+',
  '\u207b': '-',
};

const decimalPattern = '[+-]?(?:\\d+(?:\\.\\d*)?|\\.\\d+)';
const standardNumber = new RegExp(`^${decimalPattern}(?:[eE][+-]?\\d+)?$`);
const timesTenNumber = new RegExp(
  `^(${decimalPattern})\\s*[xX\\u00d7*\\u00b7]\\s*10\\s*(?:\\^)?\\s*([+-]?\\d+)$`,
);

export function parseImportNumber(value: ImportCell): number | null {
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : null;
  }

  let text = value
    .normalize('NFKC')
    .trim()
    .replace(/[\u2212\u2013]/g, '-')
    .replace(/[\u2070\u00b9\u00b2\u00b3\u2074-\u2079\u207a\u207b]/g, (character) => superscriptDigits[character]);
  if (!text) return null;

  if (/^[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?(?:[eE][+-]?\d+)?$/.test(text)) {
    text = text.replace(/,/g, '');
  }

  if (standardNumber.test(text)) {
    const parsed = Number(text);
    return Number.isFinite(parsed) ? parsed : null;
  }

  const multiplied = text.match(timesTenNumber);
  if (multiplied) {
    const parsed = Number(multiplied[1]) * (10 ** Number(multiplied[2]));
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

export function cleanImportCell(value: ImportCell): string {
  return typeof value === 'number' ? String(value) : value.trim();
}
