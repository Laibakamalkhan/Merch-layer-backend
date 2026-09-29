import React from 'react';
import { buildOnTopItems } from '../../data/siteData';
import { useIntersection } from '../../hooks/useIntersection';
import SectionLabel from '../ui/SectionLabel';
import './BuildOnTop.css';

function BuildItem({ item, index }) {
  const ref = useIntersection();
  return (
    <div className={`build-item fade-up stagger-${index + 1}`} ref={ref}>
      <div className="build-item__left">
        <h3 className="build-item__title">{item.title}</h3>
        <div className="build-item__tags">
          {item.tags.map((tag) => (
            <span key={tag} className="build-item__tag">{tag}</span>
          ))}
        </div>
      </div>
      <p className="build-item__description">{item.description}</p>
    </div>
  );
}

export default function BuildOnTop() {
  const headRef = useIntersection();

  return (
    <section className="build-on-top section" id="use-cases" aria-label="Build on top">
      <div className="container">
        <div className="build-on-top__header fade-up" ref={headRef}>
          <h2 className="build-on-top__headline">
            Commerce data becomes more<br />
            useful when it can move.
          </h2>
          <p className="build-on-top__sub">
            Use the unified data foundation wherever your business needs it.
          </p>
        </div>

        <div className="build-on-top__items">
          {buildOnTopItems.map((item, i) => (
            <BuildItem key={item.id} item={item} index={i} />
          ))}
        </div>
      </div>
    </section>
  );
}
