import React, { useCallback, useEffect, useState } from 'react';
import { FileText } from 'lucide-react';
import { api } from '../../lib/api';
import { useAuth } from '../../context/AuthContext';
import UploadCSVButton from './UploadCSVButton';

const fmtSize = (b) => (b > 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round((b || 0) / 1024))} KB`);

const STATUS_COLORS = {
  completed: '#10B981',
  ingesting: '#F59E0B',
  profiled:  '#60A5FA',
  failed:    '#F87171',
  uploaded:  '#94A3B8',
};

export default function FilesTab() {
  const { tenantId } = useAuth();
  const [files, setFiles] = useState([]);
  const [error, setError] = useState('');

  const load = useCallback(() => {
    if (!tenantId) return;
    api.datasets(tenantId).then((d) => setFiles(d?.items || [])).catch((e) => setError(e.message));
  }, [tenantId]);
  useEffect(() => { load(); }, [load]);

  return (
    <div className="workspace-files">
      <div className="workspace-connectors__header">
        <div>
          <h2 className="workspace-connectors__title">Your Files</h2>
          <p className="workspace-connectors__subtitle">Upload CSV datasets, catalogs or orders so the AI can use them as context.</p>
        </div>
        <div className="workspace-connectors__actions">
          <UploadCSVButton onUploadSuccess={load} />
        </div>
      </div>

      {error && <p role="alert" style={{ color: '#F87171' }}>⚠ {error}</p>}
      {files.length === 0 && !error && (
        <div className="workspace-files-empty">
          <FileText size={44} style={{ color: '#4b5563', marginBottom: 12 }} />
          <p style={{ fontSize: '0.95rem', fontWeight: 600, color: '#e5e7eb', margin: '0 0 6px' }}>No files uploaded yet</p>
          <p style={{ fontSize: '0.8rem', color: '#9ca3af', margin: '0 0 18px', maxWidth: 360, textAlign: 'center' }}>
            Upload CSV datasets to enable AI-powered analytics, query generation, and reports.
          </p>
          <UploadCSVButton onUploadSuccess={load} />
        </div>
      )}

      {files.length > 0 && (
        <div className="workspace-files__table-wrap">
          <table className="workspace-files__table">
            <thead>
              <tr>
                <th>File Name</th>
                <th>Entity</th>
                <th>Rows</th>
                <th>Size</th>
                <th>Status</th>
                <th>Uploaded</th>
              </tr>
            </thead>
            <tbody>
              {files.map((f) => (
                <tr key={f.id}>
                  <td className="file-name-cell">
                    <FileText size={16} className="file-icon" />
                    <span>{f.filename}</span>
                  </td>
                  <td><span className="type-tag">{f.detected_entity || f.file_type || '—'}</span></td>
                  <td><strong>{f.row_count != null ? f.row_count.toLocaleString() : '—'}</strong></td>
                  <td>{fmtSize(f.byte_size)}</td>
                  <td>
                    <span style={{ color: STATUS_COLORS[f.status] || '#94A3B8', fontWeight: 600, textTransform: 'capitalize' }}>
                      {f.status || '—'}
                    </span>
                  </td>
                  <td className="updated-cell">{new Date(f.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
