import React from 'react';
import { platforms } from '../../data/siteData';
import { useIntersection } from '../../hooks/useIntersection';
import './PlatformBar.css';

// Platform logo SVG icons
function PlatformLogo({ name }) {
  const logos = {
    Shopify: (
      <svg width="18" height="20" viewBox="0 0 18 20" fill="none">
        <path d="M15.2 4.2c0-.1-.1-.2-.2-.2-.1 0-1.9-.1-1.9-.1s-1.3-1.3-1.4-1.4c-.1-.1-.4-.1-.5 0l-.7.7C9.8 1.9 8.8 1.5 7.9 1.5c-1.9 0-2.8 2.4-3.1 3.6l-2.1.7c-.7.2-.7.2-.8.9L.6 18.5l12 2.3 6.5-1.4L15.2 4.2zM10.3 3.5l-1.1.3c0-.1 0-.2 0-.3.1-.9-.1-1.7-.4-2.3.9.1 1.5.9 1.5 2.3zM8.4 2.1c.3.6.5 1.4.4 2.3L7 4.8c.2-.9.8-2.7 1.4-2.7zM7.2 1.5c.1 0 .2 0 .3.1-.7.4-1.4 2.3-1.6 3.5l-1.7.5c.4-1.5 1.2-4.1 3-4.1z" fill="#95BF47"/>
        <path d="M15 4c-.1 0-1.9-.1-1.9-.1s-1.3-1.3-1.4-1.4c-.1-.1-.1-.1-.2-.1v18.1l6.5-1.4-2.8-15.1c0-.1-.1-.2-.2 0z" fill="#5E8E3E"/>
        <path d="M8.7 7.1L8 9.8c-.6-.3-1.3-.4-2-.4-1.6 0-1.7 1-1.7 1.3 0 1.4 3.6 1.9 3.6 5.2 0 2.6-1.6 4.2-3.8 4.2-2.6 0-3.9-1.6-3.9-1.6l.7-2.3s1.4 1.2 2.5 1.2c.8 0 1.1-.6 1.1-1 0-1.8-3-1.9-3-4.9 0-2.5 1.8-5 5.5-5 1.4.1 2 .5 2 .5z" fill="white"/>
      </svg>
    ),
    WooCommerce: (
      <svg width="22" height="14" viewBox="0 0 22 14" fill="none">
        <rect width="22" height="14" rx="4" fill="#7F54B3" opacity="0.15"/>
        <text x="3" y="10" fontFamily="Inter,sans-serif" fontWeight="700" fontSize="7" fill="#7F54B3">Woo</text>
      </svg>
    ),
    Amazon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <path d="M10 2C5.6 2 2 5.6 2 10s3.6 8 8 8 8-3.6 8-8-3.6-8-8-8z" fill="#FF9900" opacity="0.2"/>
        <path d="M4 13s1.5 1.5 6 1.5 6.5-1.5 6.5-1.5" stroke="#FF9900" strokeWidth="1.5" strokeLinecap="round"/>
        <path d="M14.5 11.5l1.5 1-1.5.5" stroke="#FF9900" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
        <text x="5.5" y="11" fontFamily="Inter,sans-serif" fontWeight="700" fontSize="5" fill="#FF9900">amzn</text>
      </svg>
    ),
    'Adobe Commerce': (
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
        <path d="M9 1L1 16h4.5L9 8l3.5 8H17L9 1z" fill="#E34400" opacity="0.8"/>
      </svg>
    ),
    'Custom REST': (
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
        <rect x="1" y="4" width="16" height="10" rx="3" stroke="var(--color-gray-400)" strokeWidth="1.3"/>
        <path d="M5 9h8M9 7v4" stroke="var(--color-gray-400)" strokeWidth="1.3" strokeLinecap="round"/>
      </svg>
    ),
    'GraphQL APIs': (
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
        <polygon points="9,1 16.5,5 16.5,13 9,17 1.5,13 1.5,5" stroke="#E535AB" strokeWidth="1.3" fill="none"/>
        <circle cx="9" cy="9" r="2" fill="#E535AB"/>
      </svg>
    ),
  };

  return logos[name] || (
    <div className="platform-logo-fallback">{name[0]}</div>
  );
}

export default function PlatformBar() {
  const ref = useIntersection();

  return (
    <div className="platform-bar fade-in" ref={ref}>
      <div className="platform-bar__inner container">
        <p className="platform-bar__label">
          Connect the platforms your business already runs on
        </p>
        <div className="platform-bar__logos">
          {platforms.map((platform) => (
            <div key={platform.id} className="platform-bar__item">
              <PlatformLogo name={platform.name} />
              <span className="platform-bar__name">{platform.name}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
