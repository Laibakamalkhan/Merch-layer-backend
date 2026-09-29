import React from 'react';
import { footerLinks } from '../../data/siteData';
import './Footer.css';

export default function Footer() {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="footer" role="contentinfo">
      <div className="footer__main container">
        {/* Brand column */}
        <div className="footer__brand">
          <a href="#" className="footer__logo" aria-label="Merchlayer home">
            <div className="footer__logo-icon" aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                <rect x="1" y="1" width="6.5" height="6.5" rx="1.5" fill="#3B82F6"/>
                <rect x="10.5" y="1" width="6.5" height="6.5" rx="1.5" fill="#60A5FA"/>
                <rect x="1" y="10.5" width="6.5" height="6.5" rx="1.5" fill="#2563EB"/>
                <rect x="10.5" y="10.5" width="6.5" height="6.5" rx="1.5" fill="#3B82F6"/>
              </svg>
            </div>
            <span className="footer__logo-text">
              <span className="footer__logo-part1">Merch</span>
              <span className="footer__logo-part2">layer</span>
            </span>
          </a>
          <p className="footer__tagline">
            One connection layer for<br />every commerce system.
          </p>
        </div>

        {/* Link columns */}
        {footerLinks.map((col) => (
          <div key={col.category} className="footer__col">
            <h3 className="footer__col-title">{col.category}</h3>
            <ul className="footer__col-links">
              {col.links.map((link) => (
                <li key={link.label}>
                  <a href={link.href} className="footer__link">{link.label}</a>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      {/* Bottom bar */}
      <div className="footer__bottom">
        <div className="footer__bottom-inner container">
          <p className="footer__copy">
            © {currentYear} Merchlayer, Inc. All rights reserved.
          </p>
          <div className="footer__status">
            <span className="footer__status-dot" aria-hidden="true" />
            <span>All systems operational</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
