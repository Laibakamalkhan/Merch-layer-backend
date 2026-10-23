import React, { useRef, useState, useEffect } from 'react';
import { Upload, Loader2, CheckCircle2, AlertCircle, X, ArrowRight, Settings } from 'lucide-react';
import { api } from '../../lib/api';
import { useAuth } from '../../context/AuthContext';
import { validateCsvFile } from '../../lib/csv';

const REQUIRED_FIELDS_BY_ENTITY = {
  orders: ['source_id'],
  products: ['source_id', 'title'],
  customers: ['source_id'],
  order_items: ['source_id'],
};

const CANONICAL_FIELDS_BY_ENTITY = {
  orders: [
    'source_id', 'order_number', 'gross_amount', 'net_amount', 'currency_code',
    'source_created_at', 'discount_amount', 'shipping_amount', 'tax_amount',
    'refunded_amount', 'status', 'financial_status', 'fulfillment_status', 'sales_channel'
  ],
  products: [
    'source_id', 'title', 'handle', 'product_type', 'vendor', 'status', 'description'
  ],
  customers: [
    'source_id', 'email', 'phone', 'first_name', 'last_name', 'display_name', 'orders_count', 'total_spent'
  ],
  order_items: [
    'source_id', 'order_id', 'product_id', 'title', 'quantity', 'gross_amount', 'net_amount'
  ]
};

export default function UploadCSVButton({
  onUploadSuccess,
  onUploadError,
  tenantId: propTenantId,
  variant = 'primary',
  size = 'md',
  buttonText = 'Upload CSV',
  loadingText = 'Uploading CSV…',
  className = '',
  showToast = true,
  children,
  disabled = false,
  ...restProps
}) {
  const { tenantId: authTenantId } = useAuth();
  const activeTenantId = propTenantId || authTenantId;

  const [isUploading, setIsUploading] = useState(false);
  const [toast, setToast] = useState(null); // { id, type: 'success' | 'error' | 'info', title, message, summary }
  const [mappingModal, setMappingModal] = useState(null); // { datasetId, entity, columns, mappings, naturalKey, rowCount, file }

  const inputRef = useRef(null);
  const toastTimeoutRef = useRef(null);

  useEffect(() => {
    if (!toast || mappingModal) return;
    if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current);

    const duration = toast.type === 'error' ? 8000 : 6000;
    toastTimeoutRef.current = setTimeout(() => {
      setToast(null);
    }, duration);

    return () => {
      if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current);
    };
  }, [toast, mappingModal]);

  const showNotification = (type, title, message, summary = null) => {
    if (!showToast) return;
    setToast({
      id: Date.now(),
      type,
      title,
      message,
      summary,
    });
  };

  const handleButtonClick = (e) => {
    e.stopPropagation();
    if (isUploading || disabled) return;
    inputRef.current?.click();
  };

  const executeIngest = async (datasetId, entity, columnMappings, naturalKey, file, rowCount) => {
    setIsUploading(true);
    const mappedColsStr = Object.entries(columnMappings).map(([k, v]) => `${k} -> ${v}`).join(', ');
    showNotification(
      'info',
      'Ingesting Dataset…',
      `Target: ${entity.toUpperCase()} | Rows: ${rowCount}`,
      `Mapped columns: ${mappedColsStr}`
    );

    try {
      const task = await api.ingestDataset(datasetId, {
        tenant_id: activeTenantId,
        target_entity: entity,
        column_mappings: columnMappings,
        natural_key_column: naturalKey || undefined,
        rebuild_rag_after_sync: true,
      });

      const state = await api.waitForSyncTask(task.task_id);
      if (state.status === 'failed') {
        throw new Error(state.error || 'Ingestion task failed on server.');
      }

      const written = state.result?.records_written ?? rowCount;
      const rejected = state.result?.records_rejected ?? 0;
      const ragStatus = state.result?.rag?.status || (state.result?.rag_error ? 'failed' : 'ok');
      const ragErr = state.result?.rag?.error_type || state.result?.rag_error || '';

      showNotification(
        'success',
        'Ingestion & RAG Completed',
        `Successfully ingested ${written} ${entity} into Silver/Gold.`,
        `RAG Index Status: [${ragStatus.toUpperCase()}]${ragErr ? ` Error: ${ragErr}` : ''} | Rejected rows: ${rejected}`
      );

      onUploadSuccess?.(state.result, file);
    } catch (err) {
      showNotification('error', 'Ingestion Failed', err.message || 'Error executing dataset ingestion.');
      onUploadError?.(err, file);
    } finally {
      setIsUploading(false);
      setMappingModal(null);
    }
  };

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;

    const validation = validateCsvFile(file);
    if (!validation.valid) {
      const err = new Error(validation.error);
      showNotification('error', 'Invalid File', validation.error);
      onUploadError?.(err, file);
      return;
    }

    if (!activeTenantId) {
      const err = new Error('No active workspace selected. Please select a workspace.');
      showNotification('error', 'Upload Failed', err.message);
      onUploadError?.(err, file);
      return;
    }

    setIsUploading(true);
    setToast(null);

    try {
      const uploadRes = await api.uploadDataset(activeTenantId, file);
      const dataset = uploadRes.dataset;
      const profile = uploadRes.profile;
      const entity = profile.detected_entity || 'orders';
      const rowCount = profile.row_count || dataset.row_count || 0;
      const suggested = profile.suggested_mappings || {};
      const columns = profile.columns || [];
      const requiredFields = REQUIRED_FIELDS_BY_ENTITY[entity] || ['source_id'];

      // Auto-apply rule:
      // 1. All required fields mapped
      // 2. Every mapped column has confidence >= 0.8
      // 3. has_validation_errors is false
      const mappedValues = Object.values(suggested);
      const allRequiredMapped = requiredFields.every((rf) => mappedValues.includes(rf));
      const hasMappings = Object.keys(suggested).length > 0;
      const allConfidenceHigh = hasMappings && Object.entries(suggested).every(([colName]) => {
        const col = columns.find((c) => c.name === colName);
        return col ? (col.confidence ?? 0) >= 0.8 : false;
      });
      const noValidationErrors = !profile.has_validation_errors;
      const canAutoApply = allRequiredMapped && allConfidenceHigh && noValidationErrors;

      if (canAutoApply) {
        // Auto-apply immediately with summary
        await executeIngest(dataset.id, entity, suggested, profile.candidate_natural_key, file, rowCount);
      } else {
        // Open interactive mapping panel
        setIsUploading(false);
        setMappingModal({
          datasetId: dataset.id,
          entity,
          columns,
          mappings: { ...suggested },
          naturalKey: profile.candidate_natural_key || '',
          rowCount,
          file,
          reason: !allRequiredMapped
            ? `Required field(s) [${requiredFields.join(', ')}] missing in auto-detection.`
            : !allConfidenceHigh
            ? 'One or more column matches had confidence < 80%.'
            : 'Validation issues detected in sample rows.',
        });
      }
    } catch (err) {
      const errorMsg = err?.message || 'Failed to upload CSV file.';
      showNotification('error', 'Upload Failed', errorMsg);
      onUploadError?.(err, file);
      setIsUploading(false);
    }
  };

  const isBtnDisabled = disabled || isUploading;
  const iconSize = size === 'sm' ? 13 : 15;
  const isPill = variant === 'pill';
  const btnClasses = [
    isPill ? 'ws-csv-upload-btn' : 'ws-btn',
    isPill ? (size === 'sm' ? 'ws-csv-upload-btn--sm' : '') : `ws-btn--${variant}`,
    !isPill && size === 'sm' ? 'ws-btn--sm' : '',
    isUploading ? 'ws-btn--loading' : '',
    className,
  ].filter(Boolean).join(' ');

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept=".csv,text/csv,application/vnd.ms-excel"
        style={{ display: 'none' }}
        onChange={handleFileChange}
        tabIndex={-1}
        aria-hidden="true"
      />

      <button
        type="button"
        className={btnClasses}
        disabled={isBtnDisabled}
        onClick={handleButtonClick}
        title={isUploading ? loadingText : buttonText}
        {...restProps}
      >
        {children ? (
          isUploading ? <Loader2 size={iconSize} className="spin-fast" /> : children
        ) : (
          <>
            {isUploading ? (
              <Loader2 size={iconSize} className="spin-fast" />
            ) : (
              <Upload size={iconSize} />
            )}
            <span>{isUploading ? loadingText : buttonText}</span>
          </>
        )}
      </button>

      {/* Review & Mapping Modal when Auto-Apply is not met */}
      {mappingModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 99999,
            backgroundColor: 'rgba(0, 0, 0, 0.75)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 16,
            backdropFilter: 'blur(4px)',
          }}
          role="dialog"
          aria-modal="true"
        >
          <div
            style={{
              backgroundColor: '#1E293B',
              color: '#F8FAFC',
              borderRadius: 12,
              padding: 24,
              maxWidth: 580,
              width: '100%',
              maxHeight: '90vh',
              overflowY: 'auto',
              boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.5)',
              border: '1px solid #334155',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <div>
                <h3 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>Review CSV Mapping</h3>
                <p style={{ margin: '4px 0 0', fontSize: 13, color: '#94A3B8' }}>
                  {mappingModal.rowCount} rows detected in <b>{mappingModal.file.name}</b>
                </p>
              </div>
              <button
                type="button"
                onClick={() => setMappingModal(null)}
                style={{ background: 'none', border: 'none', color: '#94A3B8', cursor: 'pointer' }}
              >
                <X size={18} />
              </button>
            </div>

            <div style={{ backgroundColor: '#0F172A', padding: 12, borderRadius: 8, marginBottom: 16, fontSize: 12, color: '#F59E0B' }}>
              ℹ {mappingModal.reason}
            </div>

            <div style={{ marginBottom: 16 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 500, color: '#94A3B8', marginBottom: 6 }}>
                Target Entity
              </label>
              <select
                value={mappingModal.entity}
                onChange={(e) => setMappingModal({ ...mappingModal, entity: e.target.value })}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  backgroundColor: '#0F172A',
                  color: '#F8FAFC',
                  border: '1px solid #334155',
                  borderRadius: 6,
                  fontSize: 14,
                }}
              >
                <option value="orders">Orders (Sales Mart)</option>
                <option value="products">Products</option>
                <option value="customers">Customers</option>
              </select>
            </div>

            <div style={{ marginBottom: 20 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 500, color: '#94A3B8', marginBottom: 8 }}>
                Column Mappings
              </label>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {mappingModal.columns.map((col) => {
                  const currentMapped = mappingModal.mappings[col.name] || '';
                  const canonicalOpts = CANONICAL_FIELDS_BY_ENTITY[mappingModal.entity] || CANONICAL_FIELDS_BY_ENTITY.orders;
                  return (
                    <div key={col.name} style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={col.name}>
                        {col.name}
                        {col.confidence > 0 && (
                          <span style={{ fontSize: 11, color: col.confidence >= 0.8 ? '#10B981' : '#F59E0B', marginLeft: 6 }}>
                            ({Math.round(col.confidence * 100)}%)
                          </span>
                        )}
                      </span>
                      <ArrowRight size={14} style={{ color: '#64748B' }} />
                      <select
                        value={currentMapped}
                        onChange={(e) => {
                          const val = e.target.value;
                          const updated = { ...mappingModal.mappings };
                          if (val) updated[col.name] = val;
                          else delete updated[col.name];
                          setMappingModal({ ...mappingModal, mappings: updated });
                        }}
                        style={{
                          padding: '6px 8px',
                          backgroundColor: '#0F172A',
                          color: '#F8FAFC',
                          border: '1px solid #334155',
                          borderRadius: 6,
                          fontSize: 13,
                        }}
                      >
                        <option value="">-- Ignore / Skip --</option>
                        {canonicalOpts.map((opt) => (
                          <option key={opt} value={opt}>{opt}</option>
                        ))}
                      </select>
                    </div>
                  );
                })}
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, paddingTop: 12, borderTop: '1px solid #334155' }}>
              <button
                type="button"
                onClick={() => setMappingModal(null)}
                style={{
                  padding: '8px 16px',
                  backgroundColor: 'transparent',
                  color: '#94A3B8',
                  border: '1px solid #334155',
                  borderRadius: 6,
                  cursor: 'pointer',
                  fontSize: 13,
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => {
                  executeIngest(
                    mappingModal.datasetId,
                    mappingModal.entity,
                    mappingModal.mappings,
                    mappingModal.naturalKey,
                    mappingModal.file,
                    mappingModal.rowCount
                  );
                }}
                disabled={Object.keys(mappingModal.mappings).length === 0}
                style={{
                  padding: '8px 16px',
                  backgroundColor: '#3B82F6',
                  color: '#FFFFFF',
                  border: 'none',
                  borderRadius: 6,
                  fontWeight: 500,
                  cursor: Object.keys(mappingModal.mappings).length === 0 ? 'not-allowed' : 'pointer',
                  opacity: Object.keys(mappingModal.mappings).length === 0 ? 0.5 : 1,
                  fontSize: 13,
                }}
              >
                Confirm & Ingest
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Floating Toast Notification with Before/After Summary */}
      {showToast && toast && (
        <aside className="ws-toast-container" aria-live="polite" aria-atomic="true">
          <div className={`ws-toast ws-toast--${toast.type}`} role="alert" style={{ maxWidth: 420 }}>
            <div className="ws-toast__icon">
              {toast.type === 'success' ? (
                <CheckCircle2 size={16} />
              ) : toast.type === 'error' ? (
                <AlertCircle size={16} />
              ) : (
                <Loader2 size={16} className="spin-fast" />
              )}
            </div>
            <div className="ws-toast__content">
              <span className="ws-toast__title">{toast.title}</span>
              <span className="ws-toast__msg">{toast.message}</span>
              {toast.summary && (
                <div style={{ marginTop: 4, fontSize: 11, opacity: 0.85, wordBreak: 'break-word', borderTop: '1px dashed rgba(255,255,255,0.2)', paddingTop: 4 }}>
                  {toast.summary}
                </div>
              )}
            </div>
            <button
              type="button"
              className="ws-toast__close"
              onClick={() => setToast(null)}
              aria-label="Close notification"
            >
              <X size={14} />
            </button>
          </div>
        </aside>
      )}
    </>
  );
}
