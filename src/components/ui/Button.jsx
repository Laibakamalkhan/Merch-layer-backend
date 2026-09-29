import React from 'react';
import './Button.css';

/**
 * Button - Reusable button component
 * @param {string} variant - 'primary' | 'outline' | 'outline-white' | 'ghost'
 * @param {string} size - 'sm' | 'md' | 'lg'
 * @param {boolean} withArrow - Show trailing arrow icon
 * @param {string} href - If provided, renders as anchor tag
 */
export default function Button({
  children,
  variant = 'primary',
  size = 'md',
  withArrow = false,
  href,
  onClick,
  className = '',
  type = 'button',
  ...props
}) {
  const classes = [
    'btn',
    `btn--${variant}`,
    size !== 'md' ? `btn--${size}` : '',
    className,
  ].filter(Boolean).join(' ');

  const content = (
    <>
      {children}
      {withArrow && (
        <span className="btn-arrow" aria-hidden="true">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M1 7h12M7 1l6 6-6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </span>
      )}
    </>
  );

  if (href) {
    return (
      <a href={href} className={classes} {...props}>
        {content}
      </a>
    );
  }

  return (
    <button type={type} className={classes} onClick={onClick} {...props}>
      {content}
    </button>
  );
}
