import React, { useState } from 'react';
import { 
  X, Check, Zap, Sparkles, ShieldCheck, ArrowRight, 
  Store, Database, BarChart3, Lock, CheckCircle2 
} from 'lucide-react';

export default function UpgradeModal({ isOpen, onClose }) {
  const [billingCycle, setBillingCycle] = useState('annual'); // 'monthly' | 'annual'

  if (!isOpen) return null;

  return (
    <div className="upgrade-modal-overlay" onClick={onClose} role="dialog" aria-modal="true">
      <div className="upgrade-modal" onClick={(e) => e.stopPropagation()}>
        <button className="upgrade-modal__close" onClick={onClose} aria-label="Close modal">
          <X size={18} />
        </button>

        <div className="upgrade-modal__header">
          <div className="upgrade-modal__badge">
            <Sparkles size={14} />
            <span>UNLOCK UNLIMITED COMMERCE</span>
          </div>
          <h2 className="upgrade-modal__title">Scale your stores with Merchlayer Pro</h2>
          <p className="upgrade-modal__desc">
            Connect unlimited store channels, run real-time multi-agent reasoning, and sync unified commerce schemas with sub-second latency.
          </p>

          <div className="upgrade-modal__toggle-wrap">
            <button 
              className={`upgrade-modal__toggle-btn ${billingCycle === 'monthly' ? 'upgrade-modal__toggle-btn--active' : ''}`}
              onClick={() => setBillingCycle('monthly')}
            >
              Monthly billing
            </button>
            <button 
              className={`upgrade-modal__toggle-btn ${billingCycle === 'annual' ? 'upgrade-modal__toggle-btn--active' : ''}`}
              onClick={() => setBillingCycle('annual')}
            >
              Annual billing <span className="discount-tag">Save 20%</span>
            </button>
          </div>
        </div>

        <div className="upgrade-modal__cards">
          {/* Free Current Plan */}
          <div className="upgrade-plan-card">
            <div className="upgrade-plan-card__header">
              <span className="upgrade-plan-card__name">Starter Free</span>
              <span className="upgrade-plan-card__current-tag">Current Plan</span>
            </div>
            <div className="upgrade-plan-card__price">
              <span className="price-val">$0</span>
              <span className="price-period">/ month forever</span>
            </div>
            <p className="upgrade-plan-card__sub">Basic single-store exploration and AI chat query preview.</p>

            <ul className="upgrade-plan-card__features">
              <li><CheckCircle2 size={16} className="feature-icon check" /> 1 Connected store</li>
              <li><CheckCircle2 size={16} className="feature-icon check" /> 20 AI queries per day</li>
              <li><CheckCircle2 size={16} className="feature-icon check" /> Merchlayer 1.5 model</li>
              <li><CheckCircle2 size={16} className="feature-icon check" /> 24h sync interval</li>
              <li className="disabled"><X size={16} className="feature-icon x" /> Real-time reasoning agent</li>
              <li className="disabled"><X size={16} className="feature-icon x" /> Multi-store inventory sync</li>
            </ul>

            <button className="upgrade-plan-card__btn disabled" disabled>
              Current Active Plan
            </button>
          </div>

          {/* Pro Recommended Plan */}
          <div className="upgrade-plan-card upgrade-plan-card--pro">
            <div className="pro-glow-border" />
            <div className="pro-popular-badge">
              <Zap size={12} /> MOST POPULAR
            </div>
            <div className="upgrade-plan-card__header">
              <span className="upgrade-plan-card__name">Merchlayer Pro</span>
              <span className="upgrade-plan-card__highlight-tag">Unlimited Speed</span>
            </div>
            <div className="upgrade-plan-card__price">
              <span className="price-val">{billingCycle === 'annual' ? '$79' : '$99'}</span>
              <span className="price-period">/ month {billingCycle === 'annual' ? 'billed annually' : 'billed monthly'}</span>
            </div>
            <p className="upgrade-plan-card__sub">For growing brands & multi-channel ecommerce power sellers.</p>

            <ul className="upgrade-plan-card__features">
              <li><CheckCircle2 size={16} className="feature-icon check-pro" /> <strong>Unlimited</strong> connected stores (Amazon, Shopify, Walmart, Etsy)</li>
              <li><CheckCircle2 size={16} className="feature-icon check-pro" /> <strong>Merchlayer 2.0 Reasoning & Deep Analytics</strong></li>
              <li><CheckCircle2 size={16} className="feature-icon check-pro" /> Real-time instant inventory & order sync</li>
              <li><CheckCircle2 size={16} className="feature-icon check-pro" /> Automated price matching & restock predictions</li>
              <li><CheckCircle2 size={16} className="feature-icon check-pro" /> Unlimited CSV / JSON / Webhook exports</li>
              <li><CheckCircle2 size={16} className="feature-icon check-pro" /> Priority 24/7 dedicated support</li>
            </ul>

            <button className="upgrade-plan-card__btn upgrade-plan-card__btn--pro" onClick={onClose}>
              Upgrade to Pro <ArrowRight size={16} />
            </button>
          </div>
        </div>

        <div className="upgrade-modal__footer">
          <div className="upgrade-security-note">
            <ShieldCheck size={16} />
            <span>Bank-grade 256-bit encryption · SOC2 Type II Certified · Cancel anytime</span>
          </div>
        </div>
      </div>
    </div>
  );
}
