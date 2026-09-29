import React, { useState, useEffect } from 'react';
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
import { useAuth } from './context/AuthContext';

const WORKSPACE_HASHES = ['#workspace', '#app', '#signin', '#start-flow'];
// Supabase confirmation redirect: #access_token=... ya #error=...
const isAuthCallbackHash = (h) => h.startsWith('#access_token=') || h.startsWith('#error=');

export default function App() {
  const { user, loading } = useAuth();
  const [currentView, setCurrentView] = useState(() => {
    if (typeof window !== 'undefined') {
      const hash = window.location.hash;
      if (WORKSPACE_HASHES.includes(hash) || isAuthCallbackHash(hash)) {
        return 'workspace';
      }
    }
    return 'landing';
  });

  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash;
      if (WORKSPACE_HASHES.includes(hash) || isAuthCallbackHash(hash)) {
        setCurrentView('workspace');
      } else if (hash === '#landing' || hash === '' || hash === '#') {
        setCurrentView('landing');
      }
    };

    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  const navigateToWorkspace = () => {
    setCurrentView('workspace');
    window.location.hash = '#workspace';
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const navigateToLanding = () => {
    setCurrentView('landing');
    window.location.hash = '#';
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  if (currentView === 'workspace') {
    if (loading) return <div className="auth-loading">Loading…</div>;
    if (!user) return <AuthPage onBackToLanding={navigateToLanding} />;
    return <WorkspaceView onBackToLanding={navigateToLanding} />;
  }

  return (
    <>
      <Navbar onOpenWorkspace={navigateToWorkspace} />
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
      <Footer onOpenWorkspace={navigateToWorkspace} />
    </>
  );
}

