import React, { useState } from 'react';
import './CommerceFlowDiagram.css';

const SOURCE_NODES = [
  { id: 'shopify', label: 'Shopify', y: 45, pathY: 50, color: '#2563EB' },
  { id: 'amazon', label: 'Amazon', y: 115, pathY: 120, color: '#2563EB' },
  { id: 'woocommerce', label: 'WooCommerce', y: 185, pathY: 190, color: '#2563EB' },
  { id: 'adobe', label: 'Adobe Commerce', y: 255, pathY: 260, color: '#2563EB' },
];

const DESTINATION_NODES = [
  { id: 'warehouse', label: 'Warehouse', y: 45, pathY: 50, color: '#2563EB' },
  { id: 'analytics', label: 'Analytics', y: 115, pathY: 120, color: '#2563EB' },
  { id: 'ai-apps', label: 'AI Apps', y: 185, pathY: 190, color: '#2563EB' },
  { id: 'automation', label: 'Automation', y: 255, pathY: 260, color: '#2563EB' },
];

// Left bezier paths entering center
const LEFT_PATHS = [
  { id: 'left-0', d: 'M 175,50 C 275,50 285,138 360,138', dur: 2.2, delays: [0, 1.1] },
  { id: 'left-1', d: 'M 175,120 C 255,120 275,148 360,148', dur: 2.0, delays: [0.35, 1.35] },
  { id: 'left-2', d: 'M 175,190 C 255,190 275,162 360,162', dur: 2.0, delays: [0.7, 1.7] },
  { id: 'left-3', d: 'M 175,260 C 275,260 285,172 360,172', dur: 2.2, delays: [0.15, 1.25] },
];

// Right bezier paths exiting center
const RIGHT_PATHS = [
  { id: 'right-0', d: 'M 500,138 C 575,138 585,50 685,50', dur: 2.2, delays: [1.1, 2.2] },
  { id: 'right-1', d: 'M 500,148 C 585,148 605,120 685,120', dur: 2.0, delays: [1.35, 2.35] },
  { id: 'right-2', d: 'M 500,162 C 585,162 605,190 685,190', dur: 2.0, delays: [1.7, 2.7] },
  { id: 'right-3', d: 'M 500,172 C 575,172 585,260 685,260', dur: 2.2, delays: [1.25, 2.35] },
];

export default function CommerceFlowDiagram({ className = '' }) {
  const [activeNode, setActiveNode] = useState(null);

  return (
    <div className={`flow-diagram-wrapper ${className}`} role="figure" aria-label="Commerce Data Flow Diagram">
      <div className="flow-diagram-container">
        
        {/* SVG Diagram Canvas */}
        <svg
          viewBox="0 0 860 320"
          className="flow-diagram__svg"
          preserveAspectRatio="xMidYMid meet"
        >
          <defs>
            {/* Soft glowing filter for data dots */}
            <filter id="dot-glow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur in="SourceGraphic" stdDeviation="1.5" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            
            {/* Subtle path gradient */}
            <linearGradient id="path-grad-left" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#CBD5E1" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#94A3B8" stopOpacity="0.9" />
            </linearGradient>
            <linearGradient id="path-grad-right" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#94A3B8" stopOpacity="0.9" />
              <stop offset="100%" stopColor="#CBD5E1" stopOpacity="0.8" />
            </linearGradient>
          </defs>

          {/* Connection Lines - Left */}
          <g className="flow-paths flow-paths--left">
            {LEFT_PATHS.map((path, i) => (
              <path
                key={path.id}
                id={path.id}
                d={path.d}
                className={`flow-path ${activeNode === SOURCE_NODES[i]?.id ? 'flow-path--active' : ''}`}
              />
            ))}
          </g>

          {/* Connection Lines - Right */}
          <g className="flow-paths flow-paths--right">
            {RIGHT_PATHS.map((path, i) => (
              <path
                key={path.id}
                id={path.id}
                d={path.d}
                className={`flow-path ${activeNode === DESTINATION_NODES[i]?.id ? 'flow-path--active' : ''}`}
              />
            ))}
          </g>

          {/* Animated Data Dots - Left to Center */}
          <g className="flow-dots flow-dots--left">
            {LEFT_PATHS.map((path) =>
              path.delays.map((delay, idx) => (
                <circle
                  key={`${path.id}-dot-${idx}`}
                  r="3.5"
                  className="flow-dot"
                  filter="url(#dot-glow)"
                >
                  <animateMotion
                    path={path.d}
                    dur={`${path.dur}s`}
                    begin={`${delay}s`}
                    repeatCount="indefinite"
                    calcMode="spline"
                    keySplines="0.4 0 0.2 1"
                    keyTimes="0; 1"
                  />
                  {/* Subtle opacity fade in at start and fade out at center */}
                  <animate
                    attributeName="opacity"
                    values="0; 0.95; 0.95; 0"
                    keyTimes="0; 0.15; 0.85; 1"
                    dur={`${path.dur}s`}
                    begin={`${delay}s`}
                    repeatCount="indefinite"
                  />
                </circle>
              ))
            )}
          </g>

          {/* Animated Data Dots - Center to Right */}
          <g className="flow-dots flow-dots--right">
            {RIGHT_PATHS.map((path) =>
              path.delays.map((delay, idx) => (
                <circle
                  key={`${path.id}-dot-${idx}`}
                  r="3.5"
                  className="flow-dot"
                  filter="url(#dot-glow)"
                >
                  <animateMotion
                    path={path.d}
                    dur={`${path.dur}s`}
                    begin={`${delay}s`}
                    repeatCount="indefinite"
                    calcMode="spline"
                    keySplines="0.4 0 0.2 1"
                    keyTimes="0; 1"
                  />
                  {/* Subtle opacity fade in at center and fade out at destination */}
                  <animate
                    attributeName="opacity"
                    values="0; 0.95; 0.95; 0"
                    keyTimes="0; 0.15; 0.85; 1"
                    dur={`${path.dur}s`}
                    begin={`${delay}s`}
                    repeatCount="indefinite"
                  />
                </circle>
              ))
            )}
          </g>

          {/* Source Nodes (Left) */}
          {SOURCE_NODES.map((node) => (
            <foreignObject
              key={node.id}
              x="25"
              y={node.y}
              width="150"
              height="44"
              className="flow-node-foreign"
            >
              <div
                className={`flow-node flow-node--source ${activeNode === node.id ? 'flow-node--hover' : ''}`}
                onMouseEnter={() => setActiveNode(node.id)}
                onMouseLeave={() => setActiveNode(null)}
              >
                <span>{node.label}</span>
              </div>
            </foreignObject>
          ))}

          {/* Center Processing Node (Unified Commerce Layer) */}
          <foreignObject
            x="360"
            y="118"
            width="140"
            height="74"
            className="flow-node-foreign flow-node-foreign--center"
          >
            <div
              className={`flow-center-card ${activeNode === 'center' ? 'flow-center-card--hover' : ''}`}
              onMouseEnter={() => setActiveNode('center')}
              onMouseLeave={() => setActiveNode(null)}
            >
              <div className="flow-center-card__edge flow-center-card__edge--left" />
              <div className="flow-center-card__text">
                <span className="flow-center-card__title">Unified</span>
                <span className="flow-center-card__sub">Commerce Layer</span>
              </div>
              <div className="flow-center-card__edge flow-center-card__edge--right" />
            </div>
          </foreignObject>

          {/* Destination Nodes (Right) */}
          {DESTINATION_NODES.map((node) => (
            <foreignObject
              key={node.id}
              x="685"
              y={node.y}
              width="150"
              height="44"
              className="flow-node-foreign"
            >
              <div
                className={`flow-node flow-node--dest ${activeNode === node.id ? 'flow-node--hover' : ''}`}
                onMouseEnter={() => setActiveNode(node.id)}
                onMouseLeave={() => setActiveNode(null)}
              >
                <span>{node.label}</span>
              </div>
            </foreignObject>
          ))}
        </svg>

        {/* Mobile View Stack (fallback on narrow screens where SVG foreignObject text gets too small) */}
        <div className="flow-diagram-mobile">
          <div className="flow-mobile-group">
            <span className="flow-mobile-label">Sources</span>
            <div className="flow-mobile-pills">
              {SOURCE_NODES.map((n) => (
                <div key={n.id} className="flow-node flow-node--source">
                  {n.label}
                </div>
              ))}
            </div>
          </div>

          <div className="flow-mobile-connector">
            <div className="flow-mobile-line" />
            <div className="flow-mobile-dot" />
          </div>

          <div className="flow-center-card flow-center-card--mobile">
            <span className="flow-center-card__title">Unified</span>
            <span className="flow-center-card__sub">Commerce Layer</span>
          </div>

          <div className="flow-mobile-connector">
            <div className="flow-mobile-line" />
            <div className="flow-mobile-dot" />
          </div>

          <div className="flow-mobile-group">
            <span className="flow-mobile-label">Destinations</span>
            <div className="flow-mobile-pills">
              {DESTINATION_NODES.map((n) => (
                <div key={n.id} className="flow-node flow-node--dest">
                  {n.label}
                </div>
              ))}
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
