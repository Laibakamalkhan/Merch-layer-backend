import React, { useRef, useState, useEffect } from 'react';
import { Upload, Loader2, CheckCircle2, AlertCircle, X } from 'lucide-react';
import { api } from '../../lib/api';
import { useAuth } from '../../context/AuthContext';
import { validateCsvFile } from '../../lib/csv';

/**
 * UploadCSVButton
 * Production-ready reusable component for uploading CSV datasets to the backend.
 *
 * @param {Object} props
 * @param {Function} [props.onUploadSuccess] - Callback with upload response and file
 * @param {Function} [props.onUploadError] - Callback with error and file
 * @param {string} [props.tenantId] - Optional explicit tenant/workspace ID
 * @param {string} [props.variant='primary'] - 'primary' | 'secondary'
 * @param {string} [props.size='md'] - 'sm' | 'md'
 * @param {string} [props.buttonText='Upload CSV'] - Button label text
 * @param {string} [props.loadingText='Uploading CSV…'] - Label shown during upload
 * @param {string} [props.className=''] - Additional CSS classes
 * @param {boolean} [props.showToast=true] - Whether to render notification toast
 * @param {React.ReactNode} [props.children] - Custom button content override
 * @param {boolean} [props.disabled=false] - External disabled state
 */
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
  const [toast, setToast] = useState(null); // { id, type: 'success' | 'error', title, message }
  const inputRef = useRef(null);
  const toastTimeoutRef = useRef(null);

  // Auto-dismiss toast
  useEffect(() => {
    if (!toast) return;
    if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current);

    const duration = toast.type === 'error' ? 6000 : 4000;
    toastTimeoutRef.current = setTimeout(() => {
      setToast(null);
    }, duration);

    return () => {
      if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current);
    };
  }, [toast]);

  const showNotification = (type, title, message) => {
    if (!showToast) return;
    setToast({
      id: Date.now(),
      type,
      title,
      message,
    });
  };

  const handleButtonClick = (e) => {
    e.stopPropagation();
    if (isUploading || disabled) return;
    inputRef.current?.click();
  };

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];
    // Clear input value so selecting the exact same file again triggers onChange
    e.target.value = '';
    if (!file) return;

    // 1. Client-side CSV validation
    const validation = validateCsvFile(file);
    if (!validation.valid) {
      const err = new Error(validation.error);
      showNotification('error', 'Invalid File', validation.error);
      onUploadError?.(err, file);
      return;
    }

    // 2. Validate tenant context
    if (!activeTenantId) {
      const err = new Error('No active workspace selected. Please select a workspace.');
      showNotification('error', 'Upload Failed', err.message);
      onUploadError?.(err, file);
      return;
    }

    // 3. Perform upload using existing backend API service
    setIsUploading(true);
    setToast(null);

    try {
      const result = await api.uploadCSV(activeTenantId, file);
      showNotification(
        'success',
        'Upload Successful',
        `"${file.name}" has been uploaded and queued for indexing.`
      );
      onUploadSuccess?.(result, file);
    } catch (err) {
      const errorMsg = err?.message || 'Failed to upload CSV file. Please try again.';
      showNotification('error', 'Upload Failed', errorMsg);
      onUploadError?.(err, file);
    } finally {
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

      {/* Floating Toast Notification */}
      {showToast && toast && (
        <aside className="ws-toast-container" aria-live="polite" aria-atomic="true">
          <div className={`ws-toast ws-toast--${toast.type}`} role="alert">
            <div className="ws-toast__icon">
              {toast.type === 'success' ? (
                <CheckCircle2 size={16} />
              ) : (
                <AlertCircle size={16} />
              )}
            </div>
            <div className="ws-toast__content">
              <span className="ws-toast__title">{toast.title}</span>
              <span className="ws-toast__msg">{toast.message}</span>
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
