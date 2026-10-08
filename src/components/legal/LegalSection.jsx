import React, { useState } from 'react';

export default function LegalSection({
  id,
  number,
  title,
  children,
  className = '',
}) {
  const [copied, setCopied] = useState(false);

  const handleCopyAnchor = () => {
    try {
      const url = new URL(window.location.href);
      url.hash = id;
      navigator.clipboard.writeText(url.toString());
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback
    }
  };

  return (
    <section id={id} className={`legal-section ${className}`}>
      <div className="legal-section__header">
        <div className="legal-section__title-group">
          {number && <span className="legal-section__number">{number}</span>}
          <h2 className="legal-section__title">{title}</h2>
        </div>
        <button
          type="button"
          className="legal-section__anchor-btn"
          onClick={handleCopyAnchor}
          title={copied ? 'Link copied!' : 'Copy section link'}
          aria-label={`Copy link to section ${title}`}
        >
          {copied ? (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10B981" strokeWidth="2.5">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          ) : (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
              <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
            </svg>
          )}
        </button>
      </div>

      <div className="legal-section__body">{children}</div>
    </section>
  );
}
