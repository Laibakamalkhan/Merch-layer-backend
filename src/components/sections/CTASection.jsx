import React from 'react';
import { useIntersection } from '../../hooks/useIntersection';
import Button from '../ui/Button';
import SectionLabel from '../ui/SectionLabel';
import './CTASection.css';

export default function CTASection({ onOpenWorkspace }) {
  const handleConnect = (e) => {
    if (onOpenWorkspace) {
      e.preventDefault();
      onOpenWorkspace();
    }
  };

  return (
    <section className="cta-section" id="start" aria-label="Get started">
      <div className="cta-section__inner container">
        <h2 className="cta-section__headline">
          Your commerce systems<br />
          already contain the data.<br />
          Bring it together.
        </h2>

        <p className="cta-section__sub">
          Connect your first store and start building a reliable<br className="cta-break" /> commerce data foundation.
        </p>

        <div className="cta-section__actions">
          <Button variant="primary" size="lg" withArrow href="#workspace" onClick={handleConnect}>
            Connect a store
          </Button>
          <Button variant="outline-white" size="lg" href="#contact">
            Talk to us
          </Button>
        </div>
      </div>
    </section>
  );
}
