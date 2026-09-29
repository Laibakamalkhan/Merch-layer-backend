import React from 'react';
import { useIntersection } from '../../hooks/useIntersection';
import CommerceFlowDiagram from '../ui/CommerceFlowDiagram';
import './ProblemSolution.css';

export default function ProblemSolution() {
  const leftRef = useIntersection();
  const rightRef = useIntersection();
  const diagramRef = useIntersection();

  return (
    <section className="problem-solution section" id="use-cases" aria-label="Problem and solution">
      <div className="container">
        <div className="problem-solution__top">
          <div className="problem-solution__problem fade-up" ref={leftRef}>
            <h2 className="problem-solution__heading">
              Commerce data was never designed to live in one place.
            </h2>
            <p className="problem-solution__body">
              Orders may live in Shopify, inventory in a separate system, marketplace
              transactions in Amazon, and customer data spread across multiple
              platforms. Building and maintaining separate pipelines for every source
              <span className="highlight-blue"> quickly becomes difficult to scale.</span>
            </p>
          </div>

          <div className="problem-solution__solution fade-up stagger-2" ref={rightRef}>
            <h2 className="problem-solution__heading">
              One integration layer changes that.
            </h2>
            <p className="problem-solution__body">
              Connect stores independently, discover available resources,{' '}
              <span className="highlight-blue">standardize incoming data,</span> and
              make it available through one reliable commerce data{' '}
              <span className="highlight-blue">foundation your teams can actually depend on.</span>
            </p>
          </div>
        </div>

        <div className="problem-solution__diagram fade-up" ref={diagramRef}>
          <CommerceFlowDiagram />
        </div>
      </div>
    </section>
  );
}

