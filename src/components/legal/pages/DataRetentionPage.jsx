import React from 'react';
import LegalPageLayout from '../LegalPageLayout';
import LegalSection from '../LegalSection';

const TOC_ITEMS = [
  { id: 'data-we-retain', title: 'Data We Retain' },
  { id: 'why-we-retain-data', title: 'Why We Retain Data' },
  { id: 'retention-periods', title: 'Retention Periods' },
  { id: 'account-deletion', title: 'Account Deletion' },
  { id: 'customer-data-deletion', title: 'Customer Data Deletion' },
  { id: 'shopify-amazon-connected-data', title: 'Shopify & Amazon Connected Data' },
  { id: 'backup-deletion', title: 'Backup & Archive Deletion' },
  { id: 'legal-regulatory-retention', title: 'Legal & Regulatory Retention' },
  { id: 'how-to-request-deletion', title: 'How to Request Deletion' },
  { id: 'contact', title: 'Contact Information' },
];

export default function DataRetentionPage({ onNavigate, onOpenWorkspace }) {
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
      currentPath="/data-retention"
      title="Data Retention & Deletion Policy"
      description="This Policy defines the data retention schedules, lifecycle management, and secure deletion procedures applied to commerce records, account credentials, and platform logs at Merchlayer."
      lastUpdated="[LAST UPDATED DATE]"
      tocItems={TOC_ITEMS}
      onNavigate={onNavigate}
      onOpenWorkspace={onOpenWorkspace}
    >
      {/* 1. Data We Retain */}
      <LegalSection id="data-we-retain" number="01" title="Data We Retain">
        <p>
          <span className="legal-placeholder">[LEGAL COMPANY NAME]</span> (&ldquo;<strong>Merchlayer</strong>&rdquo;, &ldquo;<strong>we</strong>&rdquo;, &ldquo;<strong>us</strong>&rdquo;, or &ldquo;<strong>our</strong>&rdquo;) processes and temporarily retains specific categories of data necessary to provide our unified commerce layer:
        </p>
        <ul>
          <li><strong>Merchant Account & Profile Data:</strong> User identity, verified email addresses, workspace configurations, and subscription status.</li>
          <li><strong>Store Connection & OAuth Tokens:</strong> Encrypted API keys, seller tokens, and webhook endpoint registration records.</li>
          <li><strong>Normalized Commerce Records:</strong> Synchronized cache of orders, products, customers, inventory levels, fulfillments, and payments extracted from connected stores.</li>
          <li><strong>System Telemetry & Audit Logs:</strong> API request metadata, pipeline execution logs, synchronization error traces, and security event histories.</li>
        </ul>
      </LegalSection>

      {/* 2. Why We Retain Data */}
      <LegalSection id="why-we-retain-data" number="02" title="Why We Retain Data">
        <p>We retain data strictly for legitimate operational purposes, including:</p>
        <ul>
          <li><strong>Service Delivery:</strong> Maintaining normalized schemas and serving fast API responses to downstream warehouses, BI dashboards, and AI workflows.</li>
          <li><strong>Incremental Synchronization:</strong> Storing change tracking hashes (cursors, timestamps) to avoid wasteful re-fetching of unchanged commerce records.</li>
          <li><strong>Dispute Resolution & Audit:</strong> Resolving discrepancies, validating API rate consumption, and maintaining platform security audit trails.</li>
          <li><strong>Statutory Compliance:</strong> Satisfying mandatory accounting, tax, and corporate governance obligations.</li>
        </ul>
      </LegalSection>

      {/* 3. Retention Periods */}
      <LegalSection id="retention-periods" number="03" title="Retention Periods">
        <p>
          The table below outlines our standard data retention schedules. Data is retained only as long as necessary for the specified purpose:
        </p>
        <div className="legal-table-wrapper">
          <table className="legal-table">
            <thead>
              <tr>
                <th>Data Classification</th>
                <th>Standard Retention Period</th>
                <th>Action at Period End</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><strong>Active Account Records</strong></td>
                <td>Duration of active account + <span className="legal-placeholder">[RETENTION PERIOD — TO BE CONFIRMED]</span></td>
                <td>Permanent cryptographic purge</td>
              </tr>
              <tr>
                <td><strong>Cached Commerce Records (Orders, Inventory)</strong></td>
                <td>Active subscription lifecycle or until store disconnect</td>
                <td>Hard delete within 30 days</td>
              </tr>
              <tr>
                <td><strong>OAuth Access Tokens & Secrets</strong></td>
                <td>Active connection duration</td>
                <td>Immediate revocation & key deletion</td>
              </tr>
              <tr>
                <td><strong>API Telemetry & Sync Logs</strong></td>
                <td><span className="legal-placeholder">[RETENTION PERIOD — TO BE CONFIRMED]</span></td>
                <td>Automated rolling truncation</td>
              </tr>
              <tr>
                <td><strong>Financial & Invoicing Invoices</strong></td>
                <td>7 years (or statutory tax requirement)</td>
                <td>Secure archive & regulatory disposal</td>
              </tr>
            </tbody>
          </table>
        </div>
      </LegalSection>

      {/* 4. Account Deletion */}
      <LegalSection id="account-deletion" number="04" title="Account Deletion">
        <p>
          When an authorized account administrator requests account deletion:
        </p>
        <ol>
          <li>All active synchronization jobs and scheduled pipeline cron triggers are immediately terminated.</li>
          <li>All OAuth tokens and store API credentials associated with the workspace are permanently revoked and erased.</li>
          <li>All workspace schemas, custom transformations, and member records are deleted from active databases within 30 days of the request.</li>
        </ol>
      </LegalSection>

      {/* 5. Customer Data Deletion */}
      <LegalSection id="customer-data-deletion" number="05" title="Customer Data Deletion">
        <p>
          In our role as a Data Processor under the{' '}
          <a href="/dpa" className="legal-link" onClick={(e) => handleLegalLink(e, '/dpa')}>
            Data Processing Agreement
          </a>
          , we honor customer-directed data deletion requests:
        </p>
        <ul>
          <li>When you disconnect an individual store, you may choose to purge all cached commerce records associated with that store immediately.</li>
          <li>When an individual end-customer exercises their Right to Erasure (GDPR / CCPA) through your store, our automated webhook receivers or manual DSAR workflows purge the corresponding customer records across our database partitions.</li>
        </ul>
      </LegalSection>

      {/* 6. Shopify / Amazon Connected Data */}
      <LegalSection id="shopify-amazon-connected-data" number="06" title="Shopify & Amazon Connected Data">
        <p>
          Merchlayer strictly complies with marketplace partner data protection and deletion mandates:
        </p>
        <ul>
          <li>
            <strong>Shopify GDPR Compliance Webhooks:</strong> We implement mandatory endpoints for <code>customers/data_request</code>, <code>customers/redact</code>, and <code>shop/redact</code>. When a <code>shop/redact</code> webhook is received following uninstallation, all store data is purged from our production databases within 48 hours.
          </li>
          <li>
            <strong>Amazon SP-API Requirements:</strong> We adhere to Amazon Data Protection Policies, ensuring Personally Identifiable Information (PII) is retained only for the minimum period necessary for order fulfillment and analytics before automatic erasure.
          </li>
        </ul>
      </LegalSection>

      {/* 7. Backup Deletion */}
      <LegalSection id="backup-deletion" number="07" title="Backup & Archive Deletion">
        <p>
          Database backups are maintained for business continuity and disaster recovery purposes on a rolling basis. When data is deleted from live production databases, residual copies in encrypted backup snapshots will naturally age out and be overwritten within our standard backup cycle (typically within 30 to 90 days).
        </p>
        <p>
          In the event that a backup snapshot must be restored, any previously deleted records are re-purged immediately following restoration.
        </p>
      </LegalSection>

      {/* 8. Legal & Regulatory Retention */}
      <LegalSection id="legal-regulatory-retention" number="08" title="Legal & Regulatory Retention">
        <p>
          Notwithstanding general deletion requests, Merchlayer may retain specific records to the extent required by applicable statutory laws, tax and accounting standards, or to protect our legal rights in active dispute proceedings.
        </p>
      </LegalSection>

      {/* 9. How to Request Deletion */}
      <LegalSection id="how-to-request-deletion" number="09" title="How to Request Deletion">
        <p>
          To request the deletion of your account, workspace, or specific commerce datasets, follow these steps:
        </p>
        <ol>
          <li>Send an email from your registered account email address to <span className="legal-placeholder">[PRIVACY EMAIL]</span> with the subject line &ldquo;Data Deletion Request&rdquo;.</li>
          <li>Include your Workspace ID, registered company name, and specific store connectors to be purged.</li>
          <li>Our privacy engineering team will verify your authorization and provide written confirmation upon completion of the purge.</li>
        </ol>
      </LegalSection>

      {/* 10. Contact */}
      <LegalSection id="contact" number="10" title="Contact Information">
        <p>
          For inquiries regarding retention periods, data purging, or our technical safeguards, please contact our Data Protection team:
        </p>
        <div className="legal-callout">
          <p>
            <strong>Company:</strong> <span className="legal-placeholder">[LEGAL COMPANY NAME]</span>
            <br />
            <strong>Privacy & Erasure Requests:</strong> <span className="legal-placeholder">[PRIVACY EMAIL]</span>
            <br />
            <strong>Customer Support:</strong> <span className="legal-placeholder">[SUPPORT EMAIL]</span>
            <br />
            <strong>Mailing Address:</strong> <span className="legal-placeholder">[COMPANY ADDRESS]</span>
          </p>
        </div>
      </LegalSection>
    </LegalPageLayout>
  );
}
