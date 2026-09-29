import React, { useEffect, useState } from 'react';
import { ArrowLeft } from 'lucide-react';
import { api } from '../../lib/api';
import { useAuth } from '../../context/AuthContext';

export default function WorkspaceHeader({ onOpenUpgrade, onBackToLanding, refreshKey }) {
  const { tenantId } = useAuth();
  const [plan, setPlan] = useState(null);
  useEffect(() => {
    if (!tenantId) return;
    api.subscription(tenantId).then((d) => setPlan(d.plan)).catch(() => setPlan(null));
  }, [tenantId, refreshKey]);
  return (
    <header className="workspace-header">
      <div className="workspace-header__left">
        <button 
          className="ws-back-landing-pill"
          onClick={onBackToLanding}
          title="Back to Landing Page"
        >
          <ArrowLeft size={13} />
          <span>Website Landing</span>
        </button>
      </div>

      <div className="workspace-header__center">
        {/* The prominent banner pill from the screenshot */}
        <button 
          className="ws-plan-badge-pill"
          onClick={onOpenUpgrade}
          title="Click to view plans and unlock all stores"
        >
          <span className="plan-name">{plan ? `${plan.name} plan` : 'Plan'}</span>
          <span className="divider">|</span>
          <span className="upgrade-link">Upgrade to unlock all stores</span>
        </button>
      </div>

      <div className="workspace-header__right">
        <button 
          className="ws-live-status-pill" 
          onClick={onOpenUpgrade}
          title="All systems operational"
        >
          <span className="status-indicator-dot" />
          <span>Unified API Active</span>
        </button>
      </div>
    </header>
  );
}
