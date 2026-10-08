import React from 'react';
import LegalPageLayout from '../LegalPageLayout';
import LegalSection from '../LegalSection';

const TOC_ITEMS = [
  { id: 'parties', title: 'Parties & Scope' },
  { id: 'definitions', title: 'Definitions' },
  { id: 'controller-processor-roles', title: 'Controller & Processor Roles' },
  { id: 'processing-instructions', title: 'Processing Instructions' },
  { id: 'categories-of-personal-data', title: 'Categories of Personal Data' },
  { id: 'categories-of-data-subjects', title: 'Categories of Data Subjects' },
  { id: 'security-measures', title: 'Technical & Organizational Security' },
  { id: 'confidentiality', title: 'Confidentiality' },
  { id: 'subprocessors', title: 'Subprocessors' },
  { id: 'international-transfers', title: 'International Data Transfers' },
  { id: 'data-breach-notification', title: 'Data Breach Notification' },
  { id: 'data-subject-requests', title: 'Data Subject Requests' },
  { id: 'data-retention-and-deletion', title: 'Data Retention & Deletion' },
  { id: 'audit-rights', title: 'Audit Rights' },
  { id: 'termination', title: 'Term & Termination' },
];

export default function DPAPage({ onNavigate, onOpenWorkspace }) {
  const handleLegalLink = (e, path) => {
    e.preventDefault();
    if (onNavigate) {
      onNavigate(path);
    } else {
      window.location.hash = path.replace('/', '#');
    }
  };

  return (
    <LegalPageLayout
      currentPath="/dpa"
      title="Data Processing Agreement (DPA)"
      description="This Data Processing Agreement establishes the contractual privacy terms and processor obligations governing the processing of personal data by Merchlayer on behalf of customers."
      lastUpdated="[LAST UPDATED DATE]"
      tocItems={TOC_ITEMS}
      onNavigate={onNavigate}
      onOpenWorkspace={onOpenWorkspace}
    >
      {/* 1. Parties */}
      <LegalSection id="parties" number="01" title="Parties & Scope">
        <p>
          This Data Processing Agreement (&ldquo;<strong>DPA</strong>&rdquo;) supplements the{' '}
          <a href="/terms" className="legal-link" onClick={(e) => handleLegalLink(e, '/terms')}>
            Terms of Service
          </a>{' '}
          entered into by and between:
        </p>
        <ul>
          <li>
            <strong>Data Processor:</strong> <span className="legal-placeholder">[LEGAL COMPANY NAME]</span> (&ldquo;<strong>Merchlayer</strong>&rdquo;, &ldquo;<strong>Processor</strong>&rdquo;), and
          </li>
          <li>
            <strong>Data Controller:</strong> The Customer entity or merchant utilizing the Merchlayer services (&ldquo;<strong>Customer</strong>&rdquo;, &ldquo;<strong>Controller</strong>&rdquo;).
          </li>
        </ul>
        <p>
          This DPA applies to the processing of Personal Data in connection with Customer’s use of the Merchlayer platform to connect e-commerce stores, normalize multi-source commerce records, and route structured data to authorized destinations.
        </p>
      </LegalSection>

      {/* 2. Definitions */}
      <LegalSection id="definitions" number="02" title="Definitions">
        <p>In this DPA, capitalized terms have the meanings assigned below:</p>
        <ul>
          <li>
            &ldquo;<strong>Applicable Data Protection Law</strong>&rdquo; means all worldwide privacy and data protection legislation applicable to the Personal Data processed hereunder, including Regulation (EU) 2016/679 (GDPR), the UK Data Protection Act 2018 (UK GDPR), the Swiss Federal Act on Data Protection (FADP), and the California Consumer Privacy Act (CCPA/CPRA).
          </li>
          <li>
            &ldquo;<strong>Personal Data</strong>&rdquo;, &ldquo;<strong>Controller</strong>&rdquo;, &ldquo;<strong>Processor</strong>&rdquo;, &ldquo;<strong>Data Subject</strong>&rdquo;, &ldquo;<strong>Processing</strong>&rdquo;, and &ldquo;<strong>Personal Data Breach</strong>&rdquo; have the meanings set forth in the GDPR.
          </li>
          <li>
            &ldquo;<strong>Subprocessor</strong>&rdquo; means any third-party infrastructure host, database provider, or service vendor engaged by Merchlayer to process Customer Personal Data.
          </li>
          <li>
            &ldquo;<strong>Standard Contractual Clauses</strong>&rdquo; or &ldquo;<strong>SCCs</strong>&rdquo; means standard contractual clauses adopted by the European Commission for international transfers of personal data.
          </li>
        </ul>
      </LegalSection>

      {/* 3. Controller and Processor Roles */}
      <LegalSection id="controller-processor-roles" number="03" title="Controller and Processor Roles">
        <p>
          The parties acknowledge and agree that with respect to Personal Data processed within connected commerce store records (e.g. customer names, delivery addresses, order numbers):
        </p>
        <ul>
          <li><strong>Customer is the Controller:</strong> Customer determines the purposes and means of processing, ensures a valid legal basis exists for processing personal data, and obtains all necessary customer consents under applicable law.</li>
          <li><strong>Merchlayer is the Processor:</strong> Merchlayer processes Customer Personal Data solely on behalf of, and in accordance with the documented instructions of, Customer.</li>
        </ul>
      </LegalSection>

      {/* 4. Processing Instructions */}
      <LegalSection id="processing-instructions" number="04" title="Processing Instructions">
        <p>
          Merchlayer shall process Customer Personal Data exclusively for the following documented purposes:
        </p>
        <ol>
          <li>Executing the configuration, data extraction, schema normalization, and synchronization tasks requested by Customer via the platform interface or APIs.</li>
          <li>Providing technical support, infrastructure maintenance, and troubleshooting as authorized by Customer.</li>
          <li>Fulfilling legal obligations required under applicable statutory laws to which Merchlayer is subject.</li>
        </ol>
        <p>
          Merchlayer shall promptly notify Customer if, in its opinion, an instruction infringes Applicable Data Protection Law.
        </p>
      </LegalSection>

      {/* 5. Categories of Personal Data */}
      <LegalSection id="categories-of-personal-data" number="05" title="Categories of Personal Data">
        <p>The Personal Data processed under this agreement includes the following categories:</p>
        <div className="legal-table-wrapper">
          <table className="legal-table">
            <thead>
              <tr>
                <th>Data Category</th>
                <th>Typical Attributes</th>
                <th>Source</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><strong>Customer Identifiers</strong></td>
                <td>First name, last name, customer ID, email address, phone number</td>
                <td>Shopify, Amazon, WooCommerce, Custom APIs</td>
              </tr>
              <tr>
                <td><strong>Order & Shipping Data</strong></td>
                <td>Delivery address, billing address, tracking numbers, line items, order totals</td>
                <td>Connected Storefronts & Marketplaces</td>
              </tr>
              <tr>
                <td><strong>Merchant Account Data</strong></td>
                <td>Account owner name, work email, organization details, API access keys</td>
                <td>Direct registration & OAuth authorizations</td>
              </tr>
            </tbody>
          </table>
        </div>
      </LegalSection>

      {/* 6. Categories of Data Subjects */}
      <LegalSection id="categories-of-data-subjects" number="06" title="Categories of Data Subjects">
        <p>Data Subjects whose personal data is processed under this DPA include:</p>
        <ul>
          <li>End customers, buyers, and consumers who place orders through Customer&rsquo;s connected commerce storefronts.</li>
          <li>Customer&rsquo;s authorized employees, developers, and administrators who access the Merchlayer workspace.</li>
        </ul>
      </LegalSection>

      {/* 7. Security Measures */}
      <LegalSection id="security-measures" number="07" title="Technical & Organizational Security Measures">
        <p>
          Merchlayer implements and maintains technical and organizational measures appropriate to the risk of processing, designed to ensure the confidentiality, integrity, availability, and resilience of processing systems:
        </p>
        <ul>
          <li><strong>Data Encryption:</strong> All Personal Data in transit is encrypted using modern TLS protocols (TLS 1.2+). Data stored at rest, including authentication secrets, is encrypted using industry-standard AES-256 algorithms.</li>
          <li><strong>Access Governance:</strong> Least-privilege role-based access controls, multi-factor authentication for technical personnel, and automatic credential revocation.</li>
          <li><strong>Network Protection:</strong> Virtual private clouds, firewalls, and segregated containerized environments preventing multi-tenant data leakage.</li>
          <li><strong>System Resiliency:</strong> Redundant infrastructure, automated health monitoring, and disaster recovery replication.</li>
        </ul>
      </LegalSection>

      {/* 8. Confidentiality */}
      <LegalSection id="confidentiality" number="08" title="Confidentiality">
        <p>
          Merchlayer ensures that all personnel authorized to process Customer Personal Data are subject to appropriate statutory or contractual confidentiality obligations and receive training in data protection practices.
        </p>
      </LegalSection>

      {/* 9. Subprocessors */}
      <LegalSection id="subprocessors" number="09" title="Subprocessors">
        <p>
          Customer provides general written authorization for Merchlayer to engage subprocessors to provide cloud infrastructure, database hosting, and platform services.
        </p>
        <p>
          Merchlayer ensures that each subprocessor enters into a written agreement imposing data protection obligations no less restrictive than those set forth in this DPA.
        </p>
        <div className="legal-callout">
          <div className="legal-callout__title">Approved Subprocessor Registry</div>
          Current hosting, database, and infrastructure providers are maintained in the official registry: <span className="legal-placeholder">[SUBPROCESSORS — TO BE CONFIRMED]</span>. Merchlayer will notify Customer of any intended changes to its subprocessor roster.
        </div>
      </LegalSection>

      {/* 10. International Data Transfers */}
      <LegalSection id="international-transfers" number="10" title="International Data Transfers">
        <p>
          Where the transfer of Personal Data involves cross-border transfers outside the European Economic Area (EEA), the United Kingdom, or Switzerland to countries without an adequate level of data protection, the parties agree that such transfers shall be governed by the standard contractual clauses (EU SCCs) or relevant adequacy mechanisms approved by the European Commission.
        </p>
      </LegalSection>

      {/* 11. Data Breach Notification */}
      <LegalSection id="data-breach-notification" number="11" title="Data Breach Notification">
        <p>
          In the event of a confirmed Personal Data Breach affecting Customer Personal Data, Merchlayer shall notify Customer without undue delay (and in any event within 48 hours of becoming aware of the incident).
        </p>
        <p>
          The notification shall provide sufficient information to enable Customer to meet its obligations to report or inform Data Protection Authorities or affected Data Subjects.
        </p>
      </LegalSection>

      {/* 12. Data Subject Requests */}
      <LegalSection id="data-subject-requests" number="12" title="Data Subject Requests">
        <p>
          Taking into account the nature of the processing, Merchlayer shall assist Customer by appropriate technical and organizational measures, insofar as this is possible, to fulfill Customer&rsquo;s obligation to respond to Data Subject requests (e.g. access, correction, erasure, or portability requests) under Applicable Data Protection Law.
        </p>
        <p>
          If a Data Subject submits a request directly to Merchlayer, Merchlayer will prompt the Data Subject to submit their request directly to Customer.
        </p>
      </LegalSection>

      {/* 13. Data Retention and Deletion */}
      <LegalSection id="data-retention-and-deletion" number="13" title="Data Retention and Deletion">
        <p>
          Upon termination of the Principal Agreement or upon written request from Customer, Merchlayer shall delete or return all Customer Personal Data, in accordance with our{' '}
          <a href="/data-retention" className="legal-link" onClick={(e) => handleLegalLink(e, '/data-retention')}>
            Data Retention & Deletion Policy
          </a>
          , unless applicable law requires retention of such personal data.
        </p>
      </LegalSection>

      {/* 14. Audit Rights */}
      <LegalSection id="audit-rights" number="14" title="Audit Rights">
        <p>
          Upon reasonable prior written notice (no less than 30 days) and not more than once per calendar year, Merchlayer shall make available to Customer information reasonably necessary to demonstrate compliance with the obligations laid down in this DPA, such as summary security reports, third-party attestations, or answers to written compliance questionnaires.
        </p>
      </LegalSection>

      {/* 15. Termination */}
      <LegalSection id="termination" number="15" title="Term & Termination">
        <p>
          This DPA shall remain in effect for the duration of Customer&rsquo;s Principal Agreement and shall automatically terminate once all Customer Personal Data has been securely returned or purged from Merchlayer processing systems.
        </p>
        <div className="legal-callout">
          <p>
            <strong>DPA Inquiries & Executed Copies:</strong> <span className="legal-placeholder">[PRIVACY EMAIL]</span>
            <br />
            <strong>Legal Entity:</strong> <span className="legal-placeholder">[LEGAL COMPANY NAME]</span>
            <br />
            <strong>Official Address:</strong> <span className="legal-placeholder">[COMPANY ADDRESS]</span>
          </p>
        </div>
      </LegalSection>
    </LegalPageLayout>
  );
}
