import React, { useState, useEffect } from 'react';
import './CookieConsent.css';

const COOKIE_STORAGE_KEY = 'merchlayer_cookie_consent_v1';

export default function CookieConsent({ onNavigate }) {
  const [visible, setVisible] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [preferences, setPreferences] = useState({
    essential: true,
    functional: true,
    analytics: false,
    marketing: false,
  });

  useEffect(() => {
    try {
      const saved = localStorage.getItem(COOKIE_STORAGE_KEY);
      if (!saved) {
        // Delay slightly for smooth page entrance
        const timer = setTimeout(() => setVisible(true), 800);
        return () => clearTimeout(timer);
      } else {
        const parsed = JSON.parse(saved);
        setPreferences((prev) => ({ ...prev, ...parsed }));
      }
    } catch {
      setVisible(true);
    }
  }, []);

  // Allow other pages (e.g. Cookie Policy page) to reopen cookie settings
  useEffect(() => {
    const handleOpenPreferences = () => {
      setModalOpen(true);
    };
    window.addEventListener('open-cookie-preferences', handleOpenPreferences);
    return () => window.removeEventListener('open-cookie-preferences', handleOpenPreferences);
  }, []);

  const saveConsent = (prefs) => {
    try {
      localStorage.setItem(COOKIE_STORAGE_KEY, JSON.stringify(prefs));
    } catch {
      // storage error fallback
    }
    setPreferences(prefs);
    setVisible(false);
    setModalOpen(false);
  };

  const handleAcceptAll = () => {
    saveConsent({
      essential: true,
      functional: true,
      analytics: true,
      marketing: true,
    });
  };

  const handleEssentialOnly = () => {
    saveConsent({
      essential: true,
      functional: false,
      analytics: false,
      marketing: false,
    });
  };

  const handleSavePreferences = () => {
    saveConsent(preferences);
  };

  const handleLinkClick = (e) => {
    e.preventDefault();
    if (onNavigate) {
      onNavigate('/cookies');
    } else {
      window.location.hash = '#cookies';
    }
  };

  return (
    <>
      {visible && !modalOpen && (
        <div className="cookie-banner-wrapper" role="region" aria-label="Cookie consent banner">
          <div className="cookie-banner">
            <div className="cookie-banner__left">
              <div className="cookie-banner__icon" aria-hidden="true">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 2a10 10 0 1 0 10 10 4 4 0 0 1-5-5 4 4 0 0 1-5-5" />
                  <path d="M8.5 8.5v.01" />
                  <path d="M16 15.5v.01" />
                  <path d="M12 12v.01" />
                  <path d="M11 17v.01" />
                  <path d="M7 13v.01" />
                </svg>
              </div>
              <div className="cookie-banner__text">
                <div className="cookie-banner__title">Cookie & Privacy Choices</div>
                <div className="cookie-banner__desc">
                  We use cookies and essential local storage to ensure core platform functionality, authenticate API sessions, and maintain your workspace state. Review our{' '}
                  <a href="/cookies" className="cookie-banner__link" onClick={handleLinkClick}>
                    Cookie Policy
                  </a>{' '}
                  for details.
                </div>
              </div>
            </div>
            <div className="cookie-banner__actions">
              <button
                type="button"
                className="cookie-btn cookie-btn--ghost"
                onClick={() => setModalOpen(true)}
              >
                Customize
              </button>
              <button
                type="button"
                className="cookie-btn cookie-btn--secondary"
                onClick={handleEssentialOnly}
              >
                Essential Only
              </button>
              <button
                type="button"
                className="cookie-btn cookie-btn--primary"
                onClick={handleAcceptAll}
              >
                Accept All
              </button>
            </div>
          </div>
        </div>
      )}

      {modalOpen && (
        <div
          className="cookie-modal-backdrop"
          role="dialog"
          aria-modal="true"
          aria-labelledby="cookie-modal-title"
          onClick={() => setModalOpen(false)}
        >
          <div className="cookie-modal" onClick={(e) => e.stopPropagation()}>
            <div className="cookie-modal__header">
              <h2 id="cookie-modal-title" className="cookie-modal__title">
                Cookie & Storage Preferences
              </h2>
              <button
                type="button"
                className="cookie-modal__close"
                onClick={() => setModalOpen(false)}
                aria-label="Close preferences"
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>

            <div className="cookie-modal__body">
              <p className="cookie-modal__intro">
                Select which categories of cookies and browser storage technologies you authorize Merchlayer to use. Essential cookies cannot be disabled as they are necessary for core security and session handling.
              </p>

              {/* Essential */}
              <div className="cookie-category-item">
                <div className="cookie-category-info">
                  <div className="cookie-category-name">
                    <span>Strictly Necessary & Authentication</span>
                    <span className="cookie-category-badge">Always Active</span>
                  </div>
                  <p className="cookie-category-desc">
                    Required for core security, user authentication, CSRF validation, and connector routing. Cannot be disabled.
                  </p>
                </div>
                <label className="cookie-switch">
                  <input type="checkbox" checked={true} disabled aria-label="Strictly Necessary Cookies (Always Active)" />
                  <span className="cookie-slider" />
                </label>
              </div>

              {/* Functional */}
              <div className="cookie-category-item">
                <div className="cookie-category-info">
                  <div className="cookie-category-name">
                    <span>Functional & Workspace State</span>
                  </div>
                  <p className="cookie-category-desc">
                    Stores active tabs, interface density, schema view preferences, and UI layout settings across sessions.
                  </p>
                </div>
                <label className="cookie-switch">
                  <input
                    type="checkbox"
                    checked={preferences.functional}
                    onChange={(e) =>
                      setPreferences((p) => ({ ...p, functional: e.target.checked }))
                    }
                    aria-label="Functional Cookies"
                  />
                  <span className="cookie-slider" />
                </label>
              </div>

              {/* Analytics */}
              <div className="cookie-category-item">
                <div className="cookie-category-info">
                  <div className="cookie-category-name">
                    <span>Aggregated Performance & Diagnostics</span>
                  </div>
                  <p className="cookie-category-desc">
                    Helps us understand platform synchronization health, latency bottlenecks, and error telemetry.
                  </p>
                </div>
                <label className="cookie-switch">
                  <input
                    type="checkbox"
                    checked={preferences.analytics}
                    onChange={(e) =>
                      setPreferences((p) => ({ ...p, analytics: e.target.checked }))
                    }
                    aria-label="Analytics and Performance Cookies"
                  />
                  <span className="cookie-slider" />
                </label>
              </div>

              {/* Marketing */}
              <div className="cookie-category-item">
                <div className="cookie-category-info">
                  <div className="cookie-category-name">
                    <span>Marketing & Attribution</span>
                  </div>
                  <p className="cookie-category-desc">
                    Used to measure referral attribution from developer documentation and integrations.
                  </p>
                </div>
                <label className="cookie-switch">
                  <input
                    type="checkbox"
                    checked={preferences.marketing}
                    onChange={(e) =>
                      setPreferences((p) => ({ ...p, marketing: e.target.checked }))
                    }
                    aria-label="Marketing and Attribution Cookies"
                  />
                  <span className="cookie-slider" />
                </label>
              </div>
            </div>

            <div className="cookie-modal__footer">
              <button
                type="button"
                className="cookie-btn cookie-btn--secondary"
                style={{ color: 'var(--color-gray-700)', background: 'var(--color-white)', borderColor: 'var(--color-gray-300)' }}
                onClick={handleEssentialOnly}
              >
                Reject Non-Essential
              </button>
              <button
                type="button"
                className="cookie-btn cookie-btn--primary"
                onClick={handleSavePreferences}
              >
                Save Preferences
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
