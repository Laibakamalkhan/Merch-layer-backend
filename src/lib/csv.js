export function rowsToCsv(rows) {
  if (!rows?.length) return '';
  const cols = Object.keys(rows[0]);
  const esc = (v) => {
    let str;
    if (v === null || v === undefined) {
      str = '—';
    } else if (typeof v === 'string') {
      str = /^[=+\-@\t\r]/.test(v) ? `'${v}` : v;
    } else if (typeof v === 'object') {
      str = JSON.stringify(v);
    } else {
      str = String(v);
    }
    return `"${str.replace(/"/g, '""')}"`;
  };
  return [cols.join(','), ...rows.map((r) => cols.map((c) => esc(r[c])).join(','))].join('\n');
}

export function downloadCsv(rows, filename = 'merchlayer-export.csv') {
  const url = URL.createObjectURL(new Blob([rowsToCsv(rows)], { type: 'text/csv' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function validateCsvFile(file, maxBytes = 25 * 1024 * 1024) {
  if (!file) {
    return { valid: false, error: 'No file selected.' };
  }
  const name = file.name || '';
  const isCsvExt = name.toLowerCase().endsWith('.csv');
  const isCsvMime = file.type === 'text/csv' || file.type === 'application/vnd.ms-excel' || file.type === 'text/plain' || file.type === '';
  
  if (!isCsvExt && !isCsvMime) {
    return { valid: false, error: 'Please select a valid CSV (.csv) file.' };
  }
  if (file.size === 0) {
    return { valid: false, error: 'The selected CSV file is empty.' };
  }
  if (file.size > maxBytes) {
    const sizeMb = (file.size / (1024 * 1024)).toFixed(1);
    const limitMb = Math.round(maxBytes / (1024 * 1024));
    return { valid: false, error: `File size (${sizeMb} MB) exceeds the ${limitMb} MB limit.` };
  }
  return { valid: true };
}

