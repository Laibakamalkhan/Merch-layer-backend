import React, { useState, useEffect, useRef } from 'react';
import { navLinks, productDropdown, developerDropdown } from '../../data/siteData';
import Button from '../ui/Button';
import './Navbar.css';

function DropdownMenu({ items, isOpen }) {
  return (
    <div className={`nav-dropdown ${isOpen ? 'nav-dropdown--open' : ''}`} role="menu">
      {items.map((item) => (
        <a
          key={item.label}
          href={item.href}
          className="nav-dropdown__item"
          role="menuitem"
        >
          <span className="nav-dropdown__item-label">{item.label}</span>
          {item.description && (
            <span className="nav-dropdown__item-desc">{item.description}</span>
          )}
        </a>
      ))}
    </div>
  );
}

function NavLink({ link, onClick }) {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const ref = useRef(null);

  const dropdownItems =
    link.label === 'Product' ? productDropdown :
    link.label === 'Developers' ? developerDropdown : null;

  useEffect(() => {
    if (!dropdownOpen) return;
    const handleClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [dropdownOpen]);

  if (!link.hasDropdown) {
    return (
      <a href={link.href} className="nav-link" onClick={onClick}>
        {link.label}
      </a>
    );
  }

  return (
    <div className="nav-link-wrapper" ref={ref}>
      <button
        className={`nav-link nav-link--dropdown ${dropdownOpen ? 'nav-link--active' : ''}`}
        onClick={() => setDropdownOpen((v) => !v)}
        aria-expanded={dropdownOpen}
        aria-haspopup="true"
      >
        {link.label}
        <svg
          className={`nav-chevron ${dropdownOpen ? 'nav-chevron--open' : ''}`}
          width="12" height="12" viewBox="0 0 12 12" fill="none"
        >
          <path d="M2 4l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      {dropdownItems && <DropdownMenu items={dropdownItems} isOpen={dropdownOpen} />}
    </div>
  );
}

export default function Navbar({ onOpenWorkspace }) {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 12);
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  // Close mobile menu on resize
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth > 900) setMobileOpen(false);
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Prevent body scroll when mobile menu is open
  useEffect(() => {
    document.body.style.overflow = mobileOpen ? 'hidden' : '';
    return () => { document.body.style.overflow = ''; };
  }, [mobileOpen]);

  const handleStartConnecting = (e) => {
    if (onOpenWorkspace) {
      e.preventDefault();
      onOpenWorkspace();
    }
  };

  return (
    <header className={`navbar ${scrolled ? 'navbar--scrolled' : ''}`} role="banner">
      <div className="navbar__inner container">
        {/* Logo */}
        <a href="#" className="navbar__logo" aria-label="Merchlayer home">
          <div className="navbar__logo-icon" aria-hidden="true">
            <svg width="20" height="20" viewBox="0 0 18 18" fill="none">
              <rect x="1" y="1" width="6.5" height="6.5" rx="1.5" fill="#3B82F6"/>
              <rect x="10.5" y="1" width="6.5" height="6.5" rx="1.5" fill="#60A5FA"/>
              <rect x="1" y="10.5" width="6.5" height="6.5" rx="1.5" fill="#2563EB"/>
              <rect x="10.5" y="10.5" width="6.5" height="6.5" rx="1.5" fill="#3B82F6"/>
            </svg>
          </div>
          <span className="navbar__logo-text">
            <span>Merch</span><span style={{ color: '#2563EB' }}>layer</span>
          </span>
        </a>

        {/* Desktop nav */}
        <nav className="navbar__nav" role="navigation" aria-label="Main navigation">
          {navLinks.map((link) => (
            <NavLink key={link.label} link={link} />
          ))}
          <button 
            type="button" 
            className="nav-link nav-link--workspace-highlight"
            onClick={handleStartConnecting}
            style={{ 
              display: 'inline-flex', 
              alignItems: 'center', 
              gap: '5px', 
              color: '#3B82F6', 
              fontWeight: 600,
              background: 'rgba(59, 130, 246, 0.08)',
              padding: '4px 10px',
              borderRadius: '999px',
              border: '1px solid rgba(59, 130, 246, 0.2)'
            }}
          >
            <span>AI Workspace</span>
            <span style={{ fontSize: '0.65rem', background: '#2563EB', color: '#fff', padding: '1px 5px', borderRadius: '4px' }}>NEW</span>
          </button>
        </nav>

        {/* Desktop actions */}
        <div className="navbar__actions">
          <button 
            type="button" 
            className="nav-link nav-link--signin" 
            onClick={handleStartConnecting}
          >
            Sign in
          </button>
          <Button variant="primary" size="sm" href="#workspace" withArrow onClick={handleStartConnecting}>
            Start connecting
          </Button>
          <button 
            className="navbar__avatar" 
            aria-label="User account" 
            onClick={handleStartConnecting}
            title="Open AI Workspace"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <circle cx="8" cy="5.5" r="2.5" stroke="currentColor" strokeWidth="1.3"/>
              <path d="M2.5 13.5c0-3 2.5-4.5 5.5-4.5s5.5 1.5 5.5 4.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
            </svg>
          </button>
        </div>

        {/* Mobile hamburger */}
        <button
          className={`navbar__hamburger ${mobileOpen ? 'navbar__hamburger--open' : ''}`}
          onClick={() => setMobileOpen((v) => !v)}
          aria-label="Toggle mobile menu"
          aria-expanded={mobileOpen}
        >
          <span />
          <span />
          <span />
        </button>
      </div>

      {/* Mobile menu */}
      <div
        className={`mobile-menu ${mobileOpen ? 'mobile-menu--open' : ''}`}
        role="dialog"
        aria-label="Mobile navigation"
        aria-modal="true"
      >
        <nav className="mobile-menu__nav">
          {navLinks.map((link) => (
            <a
              key={link.label}
              href={link.href}
              className="mobile-menu__link"
              onClick={() => setMobileOpen(false)}
            >
              {link.label}
            </a>
          ))}
          <button
            type="button"
            className="mobile-menu__link"
            style={{ color: '#3B82F6', fontWeight: 600, textAlign: 'left' }}
            onClick={(e) => {
              setMobileOpen(false);
              handleStartConnecting(e);
            }}
          >
            ✨ AI Assistant Workspace
          </button>
        </nav>
        <div className="mobile-menu__actions">
          <button 
            type="button" 
            className="mobile-menu__link" 
            onClick={(e) => {
              setMobileOpen(false);
              handleStartConnecting(e);
            }}
          >
            Sign in
          </button>
          <Button 
            variant="primary" 
            href="#workspace" 
            withArrow 
            onClick={(e) => {
              setMobileOpen(false);
              handleStartConnecting(e);
            }}
          >
            Start connecting
          </Button>
        </div>
      </div>

      {/* Mobile backdrop */}
      {mobileOpen && (
        <div
          className="mobile-backdrop"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}
    </header>
  );
}
