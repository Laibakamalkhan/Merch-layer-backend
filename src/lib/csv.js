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
