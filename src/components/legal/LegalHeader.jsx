import React, { useState } from 'react';

export default function LegalHeader({
  title,
  description,
  badge = 'Compliance & Legal',
  lastUpdated = '[LAST UPDATED DATE]',
  onNavigateLanding,
}) {
  const [copied, setCopied] = useState(false);

  const handleCopyLink = () => {
    try {
      navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback
    }
  };

  const handlePrint = () => {
    window.print();
  };

  const handleHomeClick = (e) => {
    e.preventDefault();
    if (onNavigateLanding) {
      onNavigateLanding();
    } else {
      window.location.hash = '#';
    }
  };

  return (
    <div className="legal-page-hero-bg">
      <div className="container">
        <header className="legal-header" role="banner">
          {/* Breadcrumbs */}
          <nav aria-label="Breadcrumb" className="legal-header__breadcrumbs">
            <a href="/" className="legal-header__breadcrumb-link" onClick={handleHomeClick}>
              Home
            </a>
            <span className="legal-header__breadcrumb-separator" aria-hidden="true">/</span>
            <span className="legal-header__breadcrumb-link" style={{ cursor: 'default' }}>
              Legal & Compliance
            </span>
            <span className="legal-header__breadcrumb-separator" aria-hidden="true">/</span>
            <span style={{ color: 'var(--color-gray-900)', fontWeight: 600 }}>{title}</span>
          </nav>

          {/* Badge & Title */}
          <div className="legal-header__badge-row">
            <span className="legal-badge">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
              {badge}
            </span>
            <span className="legal-badge legal-badge--neutral">
              Official Policy Document
            </span>
          </div>

          <h1 className="legal-header__title">{title}</h1>
          <p className="legal-header__description">{description}</p>

          {/* Metadata & Actions */}
          <div className="legal-header__meta-bar">
            <div className="legal-header__meta-group">
              <div className="legal-header__meta-item">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                  <line x1="16" y1="2" x2="16" y2="6" />
                  <line x1="8" y1="2" x2="8" y2="6" />
                  <line x1="3" y1="10" x2="21" y2="10" />
                </svg>
                <span>
                  Last Updated: <span className="legal-placeholder">{lastUpdated}</span>
                </span>
              </div>
              <div className="legal-header__meta-item">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10" />
                  <polyline points="12 6 12 12 16 14" />
                </svg>
                <span>Effective Date: <span className="legal-placeholder">[LAST UPDATED DATE]</span></span>
              </div>
            </div>

            <div className="legal-header__actions">
              <button
                type="button"
                className="legal-action-btn"
                onClick={handleCopyLink}
                title="Copy direct link to this policy"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
                  <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
                </svg>
                <span>{copied ? 'Copied Link!' : 'Copy Link'}</span>
              </button>

              <button
                type="button"
                className="legal-action-btn"
                onClick={handlePrint}
                title="Print or save as PDF"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polyline points="6 9 6 2 18 2 18 9" />
                  <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" />
                  <rect x="6" y="14" width="12" height="8" />
                </svg>
                <span>Print / PDF</span>
              </button>
            </div>
          </div>
        </header>
      </div>
    </div>
  );
}
