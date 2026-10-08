import React, { useState, useEffect } from 'react';
import Navbar from '../layout/Navbar';
import Footer from '../layout/Footer';
import LegalHeader from './LegalHeader';
import TableOfContents from './TableOfContents';
import './LegalStyles.css';

const ALL_LEGAL_DOCS = [
  {
    path: '/terms',
    hash: '#terms',
    title: 'Terms of Service',
    desc: 'Platform terms, usage rules, API rights, and business obligations.',
  },
  {
    path: '/privacy',
    hash: '#privacy',
    title: 'Privacy Policy',
    desc: 'How customer, order, and OAuth data is collected, used, and safeguarded.',
  },
  {
    path: '/dpa',
    hash: '#dpa',
    title: 'Data Processing Agreement',
    desc: 'GDPR & international data controller-to-processor commitments.',
  },
  {
    path: '/cookies',
    hash: '#cookies',
    title: 'Cookie Policy',
    desc: 'Essential, functional, and diagnostic cookie disclosures.',
  },
  {
    path: '/data-retention',
    hash: '#data-retention',
    title: 'Data Retention & Deletion',
    desc: 'Data lifecycles, deletion workflows, and store purge procedures.',
  },
];

export default function LegalPageLayout({
  currentPath,
  title,
  description,
  badge = 'Compliance & Legal',
  lastUpdated = '[LAST UPDATED DATE]',
  tocItems = [],
  onNavigate,
  onOpenWorkspace,
  children,
}) {
  const [activeSectionId, setActiveSectionId] = useState(tocItems[0]?.id || '');
  const [showBackToTop, setShowBackToTop] = useState(false);

  // Set document title
  useEffect(() => {
    document.title = `${title} | Merchlayer`;
    window.scrollTo(0, 0);
  }, [title]);

  // Track active section and scroll to top visibility
  useEffect(() => {
    const handleScroll = () => {
      setShowBackToTop(window.scrollY > 400);

      // Section spy
      const sectionElements = tocItems.map((it) => document.getElementById(it.id)).filter(Boolean);
      const scrollPosition = window.scrollY + 160;

      for (let i = sectionElements.length - 1; i >= 0; i--) {
        const el = sectionElements[i];
        if (el.offsetTop <= scrollPosition) {
          setActiveSectionId(el.id);
          break;
        }
      }
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, [tocItems]);

  const handleSelectSection = (id) => {
    setActiveSectionId(id);
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
      window.history.replaceState(null, '', `#${id}`);
    }
  };

  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleNavigateLanding = () => {
    if (onNavigate) {
      onNavigate('/');
    } else {
      window.location.hash = '#';
    }
  };

  const handleRelatedClick = (e, path) => {
    e.preventDefault();
    if (onNavigate) {
      onNavigate(path);
    } else {
      window.location.hash = path.replace('/', '#');
    }
  };

  const relatedDocs = ALL_LEGAL_DOCS.filter(
    (doc) => doc.path !== currentPath && doc.hash !== currentPath
  );

  return (
    <div className="legal-page-wrapper">
      <Navbar onOpenWorkspace={onOpenWorkspace} />

      <main id="main-legal-content">
        <LegalHeader
          title={title}
          description={description}
          badge={badge}
          lastUpdated={lastUpdated}
          onNavigateLanding={handleNavigateLanding}
        />

        <div className="legal-layout-container">
          {tocItems.length > 0 && (
            <TableOfContents
              items={tocItems}
              activeId={activeSectionId}
              onSelectSection={handleSelectSection}
            />
          )}

          <div className="legal-content">
            {children}

            {/* Related Legal Policies */}
            {relatedDocs.length > 0 && (
              <nav className="legal-related-nav" aria-label="Related legal policies">
                <h3 className="legal-related-nav__title">Related Compliance Documents</h3>
                <div className="legal-related-nav__grid">
                  {relatedDocs.map((doc) => (
                    <a
                      key={doc.path}
                      href={doc.path}
                      className="legal-related-card"
                      onClick={(e) => handleRelatedClick(e, doc.path)}
                    >
                      <div className="legal-related-card__title">{doc.title}</div>
                      <div className="legal-related-card__desc">{doc.desc}</div>
                    </a>
                  ))}
                </div>
              </nav>
            )}
          </div>
        </div>
      </main>

      <Footer onOpenWorkspace={onOpenWorkspace} onNavigate={onNavigate} />

      {/* Floating Back to Top */}
      <button
        type="button"
        className={`legal-back-to-top ${showBackToTop ? 'legal-back-to-top--visible' : ''}`}
        onClick={scrollToTop}
        aria-label="Back to top"
        title="Scroll back to top"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
          <polyline points="18 15 12 9 6 15" />
        </svg>
      </button>
    </div>
  );
}
