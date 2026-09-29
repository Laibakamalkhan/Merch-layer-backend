import React from 'react';
import './SectionLabel.css';

/**
 * SectionLabel - Pill badge component
 * e.g. "● 01 / UNIFY COMMERCE | COMMERCE DATA INFRASTRUCTURE"
 */
export default function SectionLabel({ number, tag, subtitle, dark = false, showDot = true }) {
  return (
    <div className={`section-label ${dark ? 'section-label--dark' : ''}`}>
      {showDot && <span className="section-label__dot" aria-hidden="true" />}
      {number && (
        <span className="section-label__number">
          {number}
          {tag && <span className="section-label__sep"> / </span>}
        </span>
      )}
      {tag && <span className="section-label__tag">{tag}</span>}
      {subtitle && (
        <>
          <span className="section-label__pipe" aria-hidden="true">|</span>
          <span className="section-label__subtitle">{subtitle}</span>
        </>
      )}
    </div>
  );
}

