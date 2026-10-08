import React from 'react';
import LegalPageLayout from '../LegalPageLayout';
import LegalSection from '../LegalSection';

const TOC_ITEMS = [
  { id: 'information-we-collect', title: 'Information We Collect' },
  { id: 'account-information', title: 'Account Information' },
  { id: 'order-and-customer-data', title: 'Order & Customer Data' },
  { id: 'oauth-and-integration-data', title: 'OAuth & Integration Data' },
  { id: 'automatically-collected-information', title: 'Automatically Collected Information' },
  { id: 'how-we-use-information', title: 'How We Use Information' },
  { id: 'how-we-share-information', title: 'How We Share Information' },
  { id: 'shopify-amazon-integrations', title: 'Shopify / Amazon Integrations' },
  { id: 'data-retention', title: 'Data Retention' },
  { id: 'security', title: 'Security' },
  { id: 'user-privacy-rights', title: 'User Privacy Rights' },
  { id: 'gdpr-rights', title: 'GDPR Rights (EU & UK)' },
  { id: 'pipeda', title: 'PIPEDA Compliance (Canada)' },
  { id: 'ccpa-cpra', title: 'CCPA / CPRA Notice (California)' },
  { id: 'childrens-privacy', title: "Children's Privacy" },
  { id: 'changes-to-policy', title: 'Changes to This Policy' },
  { id: 'contact', title: 'Contact Us' },
];

export default function PrivacyPage({ onNavigate, onOpenWorkspace }) {
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
      currentPath="/privacy"
      title="Privacy Policy"
      description="This Privacy Policy explains how Merchlayer collects, uses, processes, stores, and protects personal data when you interact with our unified commerce platform."
      lastUpdated="[LAST UPDATED DATE]"
      tocItems={TOC_ITEMS}
      onNavigate={onNavigate}
      onOpenWorkspace={onOpenWorkspace}
    >
      {/* 1. Information We Collect */}
      <LegalSection id="information-we-collect" number="01" title="Information We Collect">
        <p>
          <span className="legal-placeholder">[LEGAL COMPANY NAME]</span> (&ldquo;<strong>Merchlayer</strong>&rdquo;, &ldquo;<strong>we</strong>&rdquo;, &ldquo;<strong>us</strong>&rdquo;, or &ldquo;<strong>our</strong>&rdquo;) values your privacy. We collect information necessary to operate, maintain, and provide our unified commerce integration platform, API connectors, and developer services.
        </p>
        <p>
          Depending on your interactions with our platform, we collect information directly from you, automatically through your use of the website and APIs, and via authorized third-party commerce platforms.
        </p>
      </LegalSection>

      {/* 2. Account Information */}
      <LegalSection id="account-information" number="02" title="Account Information">
        <p>
          When you register for a Merchlayer account or manage your organizational workspace, we collect:
        </p>
        <ul>
          <li><strong>Identity Details:</strong> Full name, professional title, and organizational affiliation.</li>
          <li><strong>Contact Information:</strong> Business email address and optional contact telephone number.</li>
          <li><strong>Authentication Credentials:</strong> Passwords (salted and hashed), two-factor authentication configuration, and single sign-on (SSO) profile identifiers.</li>
          <li><strong>Billing Information:</strong> Billing address, tax identification number, and payment token identifiers processed securely through our payment service providers.</li>
        </ul>
      </LegalSection>

      {/* 3. Order and Customer Data */}
      <LegalSection id="order-and-customer-data" number="03" title="Order and Customer Data">
        <p>
          When you connect your commerce stores (such as Shopify, Amazon, WooCommerce, or custom endpoints), Merchlayer processes data resources on your behalf to normalize and standardize your commerce records. This data may include:
        </p>
        <ul>
          <li><strong>Order Details:</strong> Order IDs, purchase timestamps, financial status, fulfillment status, line items, currency codes, and transaction totals.</li>
          <li><strong>End-Customer Records:</strong> Customer identifiers, customer names, delivery/billing addresses, email addresses, and purchase history as extracted from connected storefronts.</li>
          <li><strong>Product & Catalog Data:</strong> SKUs, product titles, variant identifiers, inventory levels, prices, and vendor data.</li>
          <li><strong>Fulfillments & Refunds:</strong> Tracking numbers, carrier information, return line items, and refund transaction records.</li>
        </ul>
        <div className="legal-callout legal-callout--info">
          <div className="legal-callout__title">Processor Role</div>
          For end-customer personal data contained in connected store records, you act as the Data Controller and Merchlayer acts as a Data Processor. See our{' '}
          <a href="/dpa" className="legal-link" onClick={(e) => handleLegalLink(e, '/dpa')}>
            Data Processing Agreement (DPA)
          </a>{' '}
          for full details.
        </div>
      </LegalSection>

      {/* 4. OAuth and Integration Data */}
      <LegalSection id="oauth-and-integration-data" number="04" title="OAuth and Integration Data">
        <p>
          To establish API connections with your external commerce stores, we store and manage:
        </p>
        <ul>
          <li>OAuth 2.0 access tokens, refresh tokens, and token expiration timestamps.</li>
          <li>Store identifiers, myshopify domain names, Amazon Seller / Merchant IDs, and marketplace region endpoints.</li>
          <li>Webhook registration signatures and API endpoint configuration parameters.</li>
        </ul>
        <p>
          All access tokens and API secrets are encrypted at rest and transmitted using secure transport layer encryption.
        </p>
      </LegalSection>

      {/* 5. Automatically Collected Information */}
      <LegalSection id="automatically-collected-information" number="05" title="Automatically Collected Information">
        <p>
          When you browse our website, log into your workspace, or invoke our APIs, our systems automatically log:
        </p>
        <ul>
          <li><strong>Device & Network Data:</strong> IP address, browser type and version, operating system, and referral headers.</li>
          <li><strong>Usage & Telemetry Logs:</strong> API endpoint invocation counts, sync latency, payload sizes, error status codes, and feature usage patterns.</li>
          <li><strong>Cookies & Storage:</strong> Session tokens, CSRF tokens, and interface preferences. For complete details, review our{' '}
            <a href="/cookies" className="legal-link" onClick={(e) => handleLegalLink(e, '/cookies')}>
              Cookie Policy
            </a>.
          </li>
        </ul>
      </LegalSection>

      {/* 6. How We Use Information */}
      <LegalSection id="how-we-use-information" number="06" title="How We Use Information">
        <p>We use the collected information for the following operational purposes:</p>
        <ul>
          <li><strong>Delivering Platform Features:</strong> Authenticating store connections, executing scheduled sync pipelines, normalizing raw commerce payloads into unified schemas, and serving API queries.</li>
          <li><strong>Account Administration:</strong> Managing registrations, billing, subscriptions, access control, and customer support requests.</li>
          <li><strong>Platform Security & Monitoring:</strong> Preventing fraudulent transactions, detecting unauthorized API access, investigating security incidents, and monitoring platform uptime.</li>
          <li><strong>System Improvement:</strong> Analyzing aggregated performance metrics, identifying integration bottlenecks, and optimizing connector performance.</li>
          <li><strong>Legal & Compliance:</strong> Complying with applicable legal obligations, tax filings, and law enforcement requests where mandated.</li>
        </ul>
      </LegalSection>

      {/* 7. How We Share Information */}
      <LegalSection id="how-we-share-information" number="07" title="How We Share Information">
        <p>
          We do not sell, rent, or trade your personal information or your commerce customer records to third parties for commercial advertising. We share information only under the following limited circumstances:
        </p>
        <ul>
          <li>
            <strong>Authorized Subprocessors & Service Providers:</strong> Hosting, database infrastructure, authentication providers, and customer support tools that operate under strict data processing agreements.
          </li>
          <li>
            <strong>Customer-Directed Destinations:</strong> External data warehouses (e.g., BigQuery, Snowflake), BI tools, or webhook receivers that you explicitly configure and authorize within your workspace.
          </li>
          <li>
            <strong>Business Transfers:</strong> In connection with a merger, acquisition, financing, or sale of company assets, subject to standard confidentiality assurances.
          </li>
          <li>
            <strong>Legal Requirements:</strong> When required by valid subpoenas, court orders, or applicable regulatory mandates.
          </li>
        </ul>
      </LegalSection>

      {/* 8. Shopify / Amazon Integrations */}
      <LegalSection id="shopify-amazon-integrations" number="08" title="Shopify and Amazon Integrations">
        <p>
          When integrating with Shopify, Amazon Selling Partner APIs, or other commerce channels, Merchlayer strictly complies with partner developer terms:
        </p>
        <ul>
          <li>We only request the minimal OAuth scopes required to perform the data synchronization and schema extraction tasks you select.</li>
          <li>We honor automated data deletion webhooks (including Shopify Mandatory Compliance Webhooks for customer data deletion and shop redacts) as described in our{' '}
            <a href="/data-retention" className="legal-link" onClick={(e) => handleLegalLink(e, '/data-retention')}>
              Data Retention & Deletion Policy
            </a>.
          </li>
          <li>We do not merge cross-merchant Amazon seller data or disclose proprietary store metrics to unauthorized third parties.</li>
        </ul>
      </LegalSection>

      {/* 9. Data Retention */}
      <LegalSection id="data-retention" number="09" title="Data Retention">
        <p>
          We retain account and operational information only for as long as necessary to fulfill the purposes outlined in this policy or as required by statutory retention mandates.
        </p>
        <p>
          For detailed information regarding retention schedules, cached record lifecycles, and deletion workflows, please review our full{' '}
          <a href="/data-retention" className="legal-link" onClick={(e) => handleLegalLink(e, '/data-retention')}>
            Data Retention & Deletion Policy
          </a>.
        </p>
      </LegalSection>

      {/* 10. Security */}
      <LegalSection id="security" number="10" title="Security">
        <p>
          We employ industry-standard technical and organizational security controls designed to safeguard your information against accidental or unlawful loss, destruction, alteration, or unauthorized access:
        </p>
        <ul>
          <li><strong>Encryption in Transit:</strong> TLS 1.2 and TLS 1.3 encryption for all data transmitted across public networks and APIs.</li>
          <li><strong>Encryption at Rest:</strong> AES-256 standard encryption for stored tokens, database backups, and cached data structures.</li>
          <li><strong>Access Governance:</strong> Role-based access controls (RBAC), multi-factor authentication for production systems, and least-privilege infrastructure isolation.</li>
          <li><strong>Vulnerability Monitoring:</strong> Continuous automated dependency scanning, audit logging, and regular security patching.</li>
        </ul>
      </LegalSection>

      {/* 11. User Privacy Rights */}
      <LegalSection id="user-privacy-rights" number="11" title="User Privacy Rights">
        <p>
          Depending on your jurisdiction, you possess specific legal rights regarding your personal data:
        </p>
        <ul>
          <li><strong>Right to Access:</strong> Request confirmation of whether we process your data and obtain a copy.</li>
          <li><strong>Right to Rectification:</strong> Request correction of inaccurate or incomplete personal information.</li>
          <li><strong>Right to Erasure:</strong> Request the deletion of your account and personal records (&ldquo;right to be forgotten&rdquo;).</li>
          <li><strong>Right to Restrict or Object:</strong> Restrict or object to certain types of processing.</li>
          <li><strong>Right to Data Portability:</strong> Obtain your data in a structured, machine-readable format.</li>
        </ul>
        <p>
          To exercise these rights, submit your request to <span className="legal-placeholder">[PRIVACY EMAIL]</span>.
        </p>
      </LegalSection>

      {/* 12. GDPR Rights */}
      <LegalSection id="gdpr-rights" number="12" title="GDPR Rights (European Economic Area and UK)">
        <p>
          For individuals situated within the European Economic Area (EEA) and the United Kingdom, Merchlayer processes personal data under the following legal bases pursuant to the General Data Protection Regulation (GDPR):
        </p>
        <ul>
          <li><strong>Contract Performance:</strong> Processing necessary to fulfill our service commitments under our Terms of Service.</li>
          <li><strong>Legitimate Interests:</strong> Securing our systems, preventing abuse, and optimizing integration reliability.</li>
          <li><strong>Legal Compliance:</strong> Meeting statutory tax, accounting, and regulatory obligations.</li>
          <li><strong>Consent:</strong> Where explicit consent is obtained for non-essential cookies and marketing communications.</li>
        </ul>
        <p>
          EEA and UK users have the right to lodge a complaint with their local Data Protection Authority (DPA).
        </p>
      </LegalSection>

      {/* 13. PIPEDA */}
      <LegalSection id="pipeda" number="13" title="PIPEDA Compliance (Canada)">
        <p>
          In accordance with the Personal Information Protection and Electronic Documents Act (PIPEDA), Merchlayer adheres to the ten fair information principles: accountability, identifying purposes, consent, limiting collection, limiting use and disclosure, accuracy, safeguards, openness, individual access, and challenging compliance. Canadian residents may contact our Privacy Officer at <span className="legal-placeholder">[PRIVACY EMAIL]</span>.
        </p>
      </LegalSection>

      {/* 14. CCPA / CPRA */}
      <LegalSection id="ccpa-cpra" number="14" title="CCPA / CPRA Notice (California Residents)">
        <p>
          Under the California Consumer Privacy Act as amended by the California Privacy Rights Act (CPRA), California residents are entitled to specific disclosures:
        </p>
        <ul>
          <li><strong>No Sale or Sharing:</strong> Merchlayer does NOT sell personal information or share personal information for cross-context behavioral advertising.</li>
          <li><strong>Notice of Collection:</strong> We collect the categories of personal information described in Sections 2–5 above for the business purposes described in Section 6.</li>
          <li><strong>Non-Discrimination:</strong> We will not discriminate against you in pricing or service quality for exercising your CCPA/CPRA privacy rights.</li>
        </ul>
      </LegalSection>

      {/* 15. Children's Privacy */}
      <LegalSection id="childrens-privacy" number="15" title="Children's Privacy">
        <p>
          The Merchlayer platform is an enterprise business-to-business commerce utility and is not directed at or intended for individuals under the age of 18 (or the age of majority in your jurisdiction). We do not knowingly collect personal data from children.
        </p>
      </LegalSection>

      {/* 16. Changes to This Policy */}
      <LegalSection id="changes-to-policy" number="16" title="Changes to This Policy">
        <p>
          We may update this Privacy Policy from time to time to reflect modifications in our technical practices, connector capabilities, or legal requirements. When updates are published, we will revise the &ldquo;Last Updated&rdquo; date at the top of this document. Material changes will be communicated via email or an in-app notice.
        </p>
      </LegalSection>

      {/* 17. Contact */}
      <LegalSection id="contact" number="17" title="Contact Us">
        <p>
          If you have questions, privacy concerns, or wish to submit a data subject access request (DSAR), please contact our privacy team:
        </p>
        <div className="legal-callout">
          <p>
            <strong>Organization:</strong> <span className="legal-placeholder">[LEGAL COMPANY NAME]</span>
            <br />
            <strong>Privacy & DPO Inquiries:</strong> <span className="legal-placeholder">[PRIVACY EMAIL]</span>
            <br />
            <strong>General Support:</strong> <span className="legal-placeholder">[SUPPORT EMAIL]</span>
            <br />
            <strong>Physical Address:</strong> <span className="legal-placeholder">[COMPANY ADDRESS]</span>
          </p>
        </div>
      </LegalSection>
    </LegalPageLayout>
  );
}
