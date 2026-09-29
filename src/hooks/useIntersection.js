import { useEffect, useRef } from 'react';

/**
 * useIntersection - Returns a ref and boolean indicating if element is in view.
 * Used for scroll-triggered animations.
 */
export function useIntersection(options = {}) {
  const ref = useRef(null);
  const observedRef = useRef(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !observedRef.current) {
          el.classList.add('in-view');
          observedRef.current = true;
          observer.unobserve(el);
        }
      },
      { threshold: options.threshold || 0.15, rootMargin: options.rootMargin || '0px 0px -50px 0px' }
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, [options.threshold, options.rootMargin]);

  return ref;
}

/**
 * useScrollY - Tracks vertical scroll position for navbar effects
 */
export function useScrollY() {
  const scrollY = useRef(0);

  useEffect(() => {
    const handleScroll = () => {
      scrollY.current = window.scrollY;
    };
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return scrollY;
}
