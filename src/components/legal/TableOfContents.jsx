import React, { useState, useEffect } from 'react';

export default function TableOfContents({ items, activeId, onSelectSection }) {
  const [mobileOpen, setMobileOpen] = useState(false);

  const activeItem = items.find((it) => it.id === activeId) || items[0];

  const handleClick = (e, id) => {
    e.preventDefault();
    if (onSelectSection) {
      onSelectSection(id);
    } else {
      const el = document.getElementById(id);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth' });
        window.history.replaceState(null, '', `#${id}`);
      }
    }
    setMobileOpen(false);
  };

  return (
    <>
      {/* Mobile Accordion */}
      <div className="legal-mobile-toc" aria-label="Table of Contents Navigation">
        <button
          type="button"
          className="legal-mobile-toc__trigger"
          onClick={() => setMobileOpen((o) => !o)}
          aria-expanded={mobileOpen}
        >
          <div className="legal-mobile-toc__trigger-left">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="8" y1="6" x2="21" y2="6" />
              <line x1="8" y1="12" x2="21" y2="12" />
              <line x1="8" y1="18" x2="21" y2="18" />
              <line x1="3" y1="6" x2="3.01" y2="6" />
              <line x1="3" y1="12" x2="3.01" y2="12" />
              <line x1="3" y1="18" x2="3.01" y2="18" />
            </svg>
            <span>
              Jump to Section: <strong style={{ color: 'var(--color-brand)' }}>{activeItem?.title || 'Overview'}</strong>
            </span>
          </div>
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            style={{
              transform: mobileOpen ? 'rotate(180deg)' : 'none',
              transition: 'transform 0.2s',
            }}
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </button>

        {mobileOpen && (
          <div className="legal-mobile-toc__content">
            {items.map((item, index) => {
              const isActive = item.id === activeId;
              return (
                <a
                  key={item.id}
                  href={`#${item.id}`}
                  className={`legal-toc-item ${isActive ? 'legal-toc-item--active' : ''}`}
                  onClick={(e) => handleClick(e, item.id)}
                >
                  <span className="legal-toc-item__num">
                    {String(index + 1).padStart(2, '0')}.
                  </span>
                  <span>{item.title}</span>
                </a>
              );
            })}
          </div>
        )}
      </div>

      {/* Desktop Sticky Sidebar */}
      <aside className="legal-toc-sidebar" aria-label="Table of Contents">
        <div className="legal-toc-sidebar__header">
          <span className="legal-toc-sidebar__title">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="8" y1="6" x2="21" y2="6" />
              <line x1="8" y1="12" x2="21" y2="12" />
              <line x1="8" y1="18" x2="21" y2="18" />
              <line x1="3" y1="6" x2="3.01" y2="6" />
              <line x1="3" y1="12" x2="3.01" y2="12" />
              <line x1="3" y1="18" x2="3.01" y2="18" />
            </svg>
            Contents
          </span>
          <span className="legal-toc-sidebar__count">{items.length} sections</span>
        </div>

        <nav className="legal-toc-sidebar__nav">
          {items.map((item, index) => {
            const isActive = item.id === activeId;
            return (
              <a
                key={item.id}
                href={`#${item.id}`}
                className={`legal-toc-item ${isActive ? 'legal-toc-item--active' : ''}`}
                onClick={(e) => handleClick(e, item.id)}
              >
                <span className="legal-toc-item__num">
                  {String(index + 1).padStart(2, '0')}
                </span>
                <span>{item.title}</span>
              </a>
            );
          })}
        </nav>
      </aside>
    </>
  );
}
