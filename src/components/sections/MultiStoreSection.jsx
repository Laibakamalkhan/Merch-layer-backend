import React from 'react';
import { storeConnections, storeStats } from '../../data/siteData';
import { useIntersection } from '../../hooks/useIntersection';
import SectionLabel from '../ui/SectionLabel';
import './MultiStoreSection.css';

function StatusBadge({ status, color }) {
  return (
    <span className={`status-badge status-badge--${color}`}>
      <span className="status-badge__dot" aria-hidden="true" />
      {status}
    </span>
  );
}

function ConnectionsPanel() {
  return (
    <div className="connections-panel">
      <div className="connections-panel__header">
        <h3 className="connections-panel__title">Connections</h3>
        <button className="connections-panel__add-btn">
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M6 1v10M1 6h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          Add connection
        </button>
      </div>

      <div className="connections-panel__table-header">
        <span>Connection</span>
        <span>Platform</span>
        <span>Status</span>
        <span>Last sync</span>
      </div>

      <div className="connections-panel__rows">
        {storeConnections.map((conn) => (
          <div key={conn.id} className="connections-panel__row">
            <div className="connections-panel__conn-info">
              <span className="connections-panel__conn-name">{conn.name}</span>
              <span className="connections-panel__conn-url">{conn.url}</span>
            </div>
            <span className="connections-panel__platform">{conn.platform}</span>
            <StatusBadge status={conn.status} color={conn.statusColor} />
            <span className="connections-panel__sync">{conn.lastSync}</span>
          </div>
        ))}
      </div>

      <div className="connections-panel__footer">
        <span>3 connections · 304,857 records synced</span>
        <span className="connections-panel__footer-status">All systems operational</span>
      </div>
    </div>
  );
}

export default function MultiStoreSection() {
  const textRef = useIntersection();
  const panelRef = useIntersection();

  return (
    <section className="multistore section" id="connectors" aria-label="Multi-store management">
      <div className="container">
        <div className="multistore__inner">
          <div className="multistore__content fade-up" ref={textRef}>
            <h2 className="multistore__headline">
              One business.<br />
              Many stores.<br />
              One view.
            </h2>
            <p className="multistore__body">
              Connect multiple stores from the same platform or mix different
              commerce systems{' '}
              <span className="highlight-blue">without turning your data stack into a collection of</span>{' '}
              <span className="highlight-blue">disconnected integrations.</span>
            </p>

            <div className="multistore__stats">
              {storeStats.map((stat) => (
                <div key={stat.label} className="multistore__stat">
                  <span className="multistore__stat-value">{stat.value}</span>
                  <span className="multistore__stat-label">{stat.label}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="multistore__panel-wrapper fade-up stagger-2" ref={panelRef}>
            <ConnectionsPanel />
          </div>
        </div>
      </div>
    </section>
  );
}
