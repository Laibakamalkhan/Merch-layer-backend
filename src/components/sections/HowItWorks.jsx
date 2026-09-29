import React from 'react';
import { howItWorksSteps } from '../../data/siteData';
import { useIntersection } from '../../hooks/useIntersection';
import SectionLabel from '../ui/SectionLabel';
import './HowItWorks.css';

function StepCard({ step, index }) {
  const ref = useIntersection();
  return (
    <div
      className={`step-card fade-up stagger-${index + 1}`}
      ref={ref}
    >
      <div className="step-card__number" aria-hidden="true">{step.number}</div>
      <h3 className="step-card__title">{step.title}</h3>
      <p className="step-card__description">{step.description}</p>
      <div className="step-card__tags">
        {step.tags.map((tag) => (
          <span key={tag} className="step-card__tag">{tag}</span>
        ))}
      </div>
    </div>
  );
}

export default function HowItWorks() {
  const headRef = useIntersection();

  return (
    <section className="how-it-works section" id="how-it-works" aria-label="How it works">
      <div className="container">
        <div className="how-it-works__header fade-up" ref={headRef}>
          <h2 className="how-it-works__headline">
            Connect once.<br />
            Structure everything<br />
            downstream.
          </h2>
          <p className="how-it-works__sub">
            The experience is designed to feel simple even when the infrastructure
            underneath is sophisticated.
          </p>
        </div>

        <div className="how-it-works__steps">
          {howItWorksSteps.map((step, i) => (
            <StepCard key={step.number} step={step} index={i} />
          ))}
        </div>
      </div>
    </section>
  );
}
