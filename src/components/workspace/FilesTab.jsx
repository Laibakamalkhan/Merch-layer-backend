import React, { useCallback, useEffect, useRef, useState } from 'react';
import { FileText, Trash2, Upload } from 'lucide-react';
import { api } from '../../lib/api';
import { useAuth } from '../../context/AuthContext';

const fmtSize = (b) => (b > 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round((b || 0) / 1024))} KB`);

export default function FilesTab() {
  const { tenantId } = useAuth();
  const [files, setFiles] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const inputRef = useRef(null);

  const load = useCallback(() => {
    api.files(tenantId).then((d) => setFiles(d.items)).catch((e) => setError(e.message));
  }, [tenantId]);
  useEffect(() => { load(); }, [load]);

  const onPick = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setBusy(true); setError('');
    try { await api.uploadFile(tenantId, file); load(); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };

  const remove = async (id) => {
    try { await api.deleteFile(id, tenantId); load(); } catch (err) { setError(err.message); }
  };

  return (
    <div className="workspace-files">
      <div className="workspace-connectors__header">
        <div>
          <h2 className="workspace-connectors__title">Your Files</h2>
          <p className="workspace-connectors__subtitle">Upload CSV, PDF or text files so the AI can use them as context.</p>
        </div>
        <div className="workspace-connectors__actions">
          <input ref={inputRef} type="file" hidden onChange={onPick} />
          <button className="ws-btn ws-btn--primary" disabled={busy} onClick={() => inputRef.current?.click()}>
            <Upload size={15} /><span>{busy ? 'Uploading…' : 'Upload file'}</span>
          </button>
        </div>
      </div>

      {error && <p role="alert" style={{ color: '#F87171' }}>⚠ {error}</p>}
      {files.length === 0 && !error && <p style={{ opacity: .7 }}>No files yet.</p>}

      {files.length > 0 && (
        <div className="workspace-files__table-wrap">
          <table className="workspace-files__table">
            <thead><tr><th>File Name</th><th>Type</th><th>Size</th><th>Index</th><th>Uploaded</th><th>Action</th></tr></thead>
            <tbody>
              {files.map((f) => (
                <tr key={f.id}>
                  <td className="file-name-cell"><FileText size={16} className="file-icon" /><span>{f.metadata?.filename || f.title}</span></td>
                  <td><span className="type-tag">{f.metadata?.mime_type || '—'}</span></td>
                  <td><strong>{fmtSize(f.metadata?.size_bytes)}</strong></td>
                  <td>{f.metadata?.index_status || '—'}</td>
                  <td className="updated-cell">{new Date(f.created_at).toLocaleString()}</td>
                  <td><button className="download-file-btn" onClick={() => remove(f.id)}><Trash2 size={14} /> Delete</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
