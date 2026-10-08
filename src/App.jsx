import React, { useState, useEffect, useCallback } from 'react';
import './styles/animations.css';

import Navbar from './components/layout/Navbar';
import Footer from './components/layout/Footer';
import HeroSection from './components/sections/HeroSection';
import PlatformBar from './components/sections/PlatformBar';
import ProblemSolution from './components/sections/ProblemSolution';
import HowItWorks from './components/sections/HowItWorks';
import MultiStoreSection from './components/sections/MultiStoreSection';
import DataSchemaSection from './components/sections/DataSchemaSection';
import BuildOnTop from './components/sections/BuildOnTop';
import FAQSection from './components/sections/FAQSection';
import CTASection from './components/sections/CTASection';
import WorkspaceView from './components/workspace/WorkspaceView';
import AuthPage from './components/auth/AuthPage';
import CookieConsent from './components/legal/CookieConsent';

import TermsPage from './components/legal/pages/TermsPage';
import PrivacyPage from './components/legal/pages/PrivacyPage';
import DPAPage from './components/legal/pages/DPAPage';
import CookiePolicyPage from './components/legal/pages/CookiePolicyPage';
import DataRetentionPage from './components/legal/pages/DataRetentionPage';

import { useAuth } from './context/AuthContext';

const WORKSPACE_HASHES = ['#workspace', '#app', '#signin', '#start-flow'];
// Supabase confirmation redirect: #access_token=... ya #error=...
const isAuthCallbackHash = (h) => h.startsWith('#access_token=') || h.startsWith('#error=');

const LEGAL_ROUTES = {
  '/terms': 'terms',
  '#terms': 'terms',
  '/privacy': 'privacy',
  '#privacy': 'privacy',
  '/dpa': 'dpa',
  '#dpa': 'dpa',
  '/cookies': 'cookies',
  '#cookies': 'cookies',
  '/data-retention': 'data-retention',
  '#data-retention': 'data-retention',
};

function getViewFromLocation() {
  if (typeof window === 'undefined') return 'landing';

  const pathname = window.location.pathname.toLowerCase().replace(/\/$/, '') || '/';
  const hash = window.location.hash.toLowerCase();

  // Check path routes
  if (LEGAL_ROUTES[pathname]) {
    return LEGAL_ROUTES[pathname];
  }

  // Check hash routes
  if (WORKSPACE_HASHES.includes(hash) || isAuthCallbackHash(hash)) {
    return 'workspace';
  }

  if (LEGAL_ROUTES[hash]) {
    return LEGAL_ROUTES[hash];
  }

  return 'landing';
}

export default function App() {
  const { user, loading } = useAuth();
  const [currentView, setCurrentView] = useState(() => getViewFromLocation());

  const handleRouteSync = useCallback(() => {
    const nextView = getViewFromLocation();
    setCurrentView(nextView);
  }, []);

  useEffect(() => {
    window.addEventListener('hashchange', handleRouteSync);
    window.addEventListener('popstate', handleRouteSync);
    return () => {
      window.removeEventListener('hashchange', handleRouteSync);
      window.removeEventListener('popstate', handleRouteSync);
    };
  }, [handleRouteSync]);

  const handleNavigate = (target) => {
    if (!target) return;

    // Handle workspace
    if (target === '#workspace' || target === '#app') {
      setCurrentView('workspace');
      window.location.hash = '#workspace';
      window.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }

    // Handle legal pages
    const cleanedTarget = target.toLowerCase().replace(/\/$/, '') || '/';
    if (LEGAL_ROUTES[cleanedTarget]) {
      const viewName = LEGAL_ROUTES[cleanedTarget];
      setCurrentView(viewName);
      if (cleanedTarget.startsWith('/')) {
        window.history.pushState(null, '', cleanedTarget);
      } else {
        window.location.hash = cleanedTarget;
      }
      window.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }

    // Handle landing or landing anchor links
    if (target === '/' || target === '#' || target === '#landing') {
      setCurrentView('landing');
      window.history.pushState(null, '', '/');
      window.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }

    if (target.startsWith('#')) {
      setCurrentView('landing');
      if (currentView !== 'landing') {
        window.history.pushState(null, '', '/');
        setTimeout(() => {
          const el = document.getElementById(target.substring(1));
          if (el) el.scrollIntoView({ behavior: 'smooth' });
        }, 100);
      } else {
        const el = document.getElementById(target.substring(1));
        if (el) el.scrollIntoView({ behavior: 'smooth' });
      }
    }
  };

  const navigateToWorkspace = () => {
    setCurrentView('workspace');
    window.location.hash = '#workspace';
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const navigateToLanding = () => {
    setCurrentView('landing');
    window.history.pushState(null, '', '/');
    window.location.hash = '#';
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <>
      {/* Workspace View */}
      {currentView === 'workspace' && (
        loading ? (
          <div className="auth-loading">Loading…</div>
        ) : !user ? (
          <AuthPage onBackToLanding={navigateToLanding} />
        ) : (
          <WorkspaceView onBackToLanding={navigateToLanding} />
        )
      )}

      {/* Terms of Service */}
      {currentView === 'terms' && (
        <TermsPage
          onNavigate={handleNavigate}
          onOpenWorkspace={navigateToWorkspace}
        />
      )}

      {/* Privacy Policy */}
      {currentView === 'privacy' && (
        <PrivacyPage
          onNavigate={handleNavigate}
          onOpenWorkspace={navigateToWorkspace}
        />
      )}

      {/* Data Processing Agreement */}
      {currentView === 'dpa' && (
        <DPAPage
          onNavigate={handleNavigate}
          onOpenWorkspace={navigateToWorkspace}
        />
      )}

      {/* Cookie Policy */}
      {currentView === 'cookies' && (
        <CookiePolicyPage
          onNavigate={handleNavigate}
          onOpenWorkspace={navigateToWorkspace}
        />
      )}

      {/* Data Retention & Deletion Policy */}
      {currentView === 'data-retention' && (
        <DataRetentionPage
          onNavigate={handleNavigate}
          onOpenWorkspace={navigateToWorkspace}
        />
      )}

      {/* Landing Page */}
      {currentView === 'landing' && (
        <>
          <Navbar onOpenWorkspace={navigateToWorkspace} onNavigate={handleNavigate} />
          <main id="main-content">
            <HeroSection onOpenWorkspace={navigateToWorkspace} />
            <PlatformBar />
            <ProblemSolution />
            <HowItWorks />
            <MultiStoreSection />
            <DataSchemaSection />
            <BuildOnTop />
            <FAQSection />
            <CTASection onOpenWorkspace={navigateToWorkspace} />
          </main>
          <Footer onOpenWorkspace={navigateToWorkspace} onNavigate={handleNavigate} />
        </>
      )}

      {/* Global Cookie Consent Banner */}
      <CookieConsent onNavigate={handleNavigate} />
    </>
  );
}
