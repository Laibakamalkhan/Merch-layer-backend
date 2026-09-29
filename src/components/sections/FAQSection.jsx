import React, { useState } from 'react';
import { faqItems } from '../../data/siteData';
import { useIntersection } from '../../hooks/useIntersection';
import SectionLabel from '../ui/SectionLabel';
import './FAQSection.css';

function AccordionItem({ item, isOpen, onToggle }) {
  return (
    <div className={`faq-item ${isOpen ? 'faq-item--open' : ''}`}>
      <button
        className="faq-item__question"
        onClick={onToggle}
        aria-expanded={isOpen}
        id={`faq-btn-${item.id}`}
        aria-controls={`faq-answer-${item.id}`}
      >
        <span>{item.question}</span>
        <span className="faq-item__icon" aria-hidden="true">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path
              d={isOpen ? 'M3 8h10' : 'M8 3v10M3 8h10'}
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </svg>
        </span>
      </button>
      <div
        className="faq-item__answer-wrapper"
        id={`faq-answer-${item.id}`}
        role="region"
        aria-labelledby={`faq-btn-${item.id}`}
        style={{ '--answer-height': isOpen ? 'auto' : '0px' }}
      >
        <p className="faq-item__answer">{item.answer}</p>
      </div>
    </div>
  );
}

export default function FAQSection() {
  const [openId, setOpenId] = useState(null);
  const ref = useIntersection();

  const handleToggle = (id) => {
    setOpenId((current) => (current === id ? null : id));
  };

  return (
    <section className="faq section" id="faq" aria-label="Frequently asked questions">
      <div className="container">
        <div className="faq__inner">
          <div className="faq__header fade-up" ref={ref}>
            <h2 className="faq__headline">
              Common questions,<br />clearly answered.
            </h2>
            <p className="faq__note">
              If you have a question not listed here,{' '}
              <a href="#contact" className="faq__link">reach out</a>{' '}
              and we will get back to you.
            </p>
          </div>

          <div className="faq__accordion" role="list">
            {faqItems.map((item) => (
              <AccordionItem
                key={item.id}
                item={item}
                isOpen={openId === item.id}
                onToggle={() => handleToggle(item.id)}
              />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
