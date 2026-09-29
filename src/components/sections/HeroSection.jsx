import React, { useState } from 'react';
import Button from '../ui/Button';
import SectionLabel from '../ui/SectionLabel';
import './HeroSection.css';

const PLATFORMS = [
  { id: 'shopify', name: 'Shopify', placeholder: 'my-store.myshopify.com', defaultUrl: 'acme-apparel.myshopify.com' },
  { id: 'woocommerce', name: 'WooCommerce', placeholder: 'yourstore.com/wp-json/wc/v3', defaultUrl: 'shop.fashionhub.co/wp-json/wc/v3' },
  { id: 'amazon', name: 'Amazon', placeholder: 'Seller ID: A2EQGS1...', defaultUrl: 'Seller ID: A1F83G9204K' },
  { id: 'adobe', name: 'Adobe Commerce', placeholder: 'magento.enterprise.com/rest/V1', defaultUrl: 'store.enterprise.com/rest/V1' },
  { id: 'custom', name: 'Custom API', placeholder: 'https://api.yourcommerce.com/v1', defaultUrl: 'https://api.merchlayer.internal/v1' },
];

function ConnectionMockup() {
  const [selectedPlatform, setSelectedPlatform] = useState(null);
  const [inputValue, setInputValue] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);

  const handlePlatformSelect = (plat) => {
    setSelectedPlatform(plat);
    setInputValue(plat.defaultUrl);
    setIsConnected(false);
    setIsConnecting(false);
  };

  const handleConnect = (e) => {
    e.preventDefault();
    if (!inputValue.trim()) return;
    setIsConnecting(true);
    setTimeout(() => {
      setIsConnecting(false);
      setIsConnected(true);
    }, 1200);
  };

  const handleReset = () => {
    setSelectedPlatform(null);
    setInputValue('');
    setIsConnected(false);
    setIsConnecting(false);
  };

  return (
    <div className="hero-mockup" role="region" aria-label="Interactive Connection Preview">
      {/* Window chrome header */}
      <div className="hero-mockup__chrome">
        <div className="hero-mockup__dots" aria-hidden="true">
          <span className="hero-mockup__dot hero-mockup__dot--red" />
          <span className="hero-mockup__dot hero-mockup__dot--yellow" />
          <span className="hero-mockup__dot hero-mockup__dot--green" />
        </div>
        <div className="hero-mockup__title">
          New connection — Merchlayer
        </div>
      </div>

      {/* Mockup Body */}
      <div className="hero-mockup__body">
        <p className="hero-mockup__label">SELECT PLATFORM</p>
        
        {/* Platform selection pills */}
        <div className="hero-mockup__platforms" role="tablist">
          {PLATFORMS.map((plat) => {
            const isSelected = selectedPlatform?.id === plat.id;
            return (
              <button
                key={plat.id}
                type="button"
                role="tab"
                aria-selected={isSelected}
                className={`hero-mockup__platform-btn ${isSelected ? 'hero-mockup__platform-btn--active' : ''}`}
                onClick={() => handlePlatformSelect(plat)}
              >
                {plat.name}
              </button>
            );
          })}
        </div>

        {/* Dynamic state below pills */}
        <div className="hero-mockup__action-area">
          {!selectedPlatform ? (
            <div className="hero-mockup__hint">
              Select a platform above to configure your connection.
            </div>
          ) : isConnected ? (
            <div className="hero-mockup__status-card">
              <div className="hero-mockup__status-info">
                <span className="hero-mockup__live-dot" />
                <span className="hero-mockup__status-text">
                  Connected to <strong className="hero-mockup__highlight">{inputValue}</strong>
                </span>
                <span className="hero-mockup__status-badge">Live Sync Active</span>
              </div>
              <button
                type="button"
                className="hero-mockup__reset-btn"
                onClick={handleReset}
                title="Disconnect"
              >
                Disconnect
              </button>
            </div>
          ) : (
            <form className="hero-mockup__form" onSubmit={handleConnect}>
              <div className="hero-mockup__input-wrap">
                <input
                  type="text"
                  className="hero-mockup__input"
                  placeholder={selectedPlatform.placeholder}
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  autoFocus
                />
              </div>
              <button
                type="submit"
                className={`hero-mockup__connect-submit ${isConnecting ? 'hero-mockup__connect-submit--loading' : ''}`}
                disabled={isConnecting || !inputValue.trim()}
              >
                {isConnecting ? (
                  <>
                    <svg className="hero-mockup__spin" width="13" height="13" viewBox="0 0 16 16" fill="none">
                      <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="2" strokeDasharray="24 10" />
                    </svg>
                    <span>Connecting...</span>
                  </>
                ) : (
                  'Connect'
                )}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}

export default function HeroSection({ onOpenWorkspace }) {
  const handleStart = (e) => {
    if (onOpenWorkspace) {
      e.preventDefault();
      onOpenWorkspace();
    }
  };

  return (
    <section className="hero" id="product" aria-label="Hero Section">
      {/* Background Dot Matrix Pattern */}
      <div className="hero__pattern" aria-hidden="true" />
      <div className="hero__glow" aria-hidden="true" />

      <div className="hero__container container">
        <div className="hero__content">
          {/* Main Headline */}

          {/* Main Headline */}
          <h1 className="hero__headline">
            One connection layer for<br className="hero__br-desktop" /> every commerce system.
          </h1>

          {/* Subtitle */}
          <p className="hero__sub">
            Connect stores, marketplaces and commerce APIs, then bring
            orders, customers, products, inventory and more into one
            centralized source of truth.
          </p>

          {/* CTA Buttons */}
          <div className="hero__ctas">
            <Button variant="primary" size="lg" withArrow href="#workspace" onClick={handleStart}>
              Start connecting
            </Button>
            <Button variant="outline" size="lg" href="#platform">
              Explore the platform
            </Button>
          </div>
        </div>

        {/* Interactive Mockup Window */}
        <div className="hero__mockup-wrapper">
          <ConnectionMockup />

          {/* Trust points underneath */}
          <p className="hero__trust">
            <span>No credit card required</span>
            <span className="hero__trust-dot" aria-hidden="true">·</span>
            <span>Works with existing stores</span>
            <span className="hero__trust-dot" aria-hidden="true">·</span>
            <span>SOC 2 compliant</span>
          </p>
        </div>
      </div>
    </section>
  );
}

