import React from 'react';
import LegalPageLayout from '../LegalPageLayout';
import LegalSection from '../LegalSection';

const TOC_ITEMS = [
  { id: 'acceptance-of-terms', title: 'Acceptance of Terms' },
  { id: 'account-registration', title: 'Account Registration' },
  { id: 'use-of-merchlayer', title: 'Use of Merchlayer' },
  { id: 'shopify-amazon-integrations', title: 'Shopify & Amazon Integrations' },
  { id: 'acceptable-use', title: 'Acceptable Use' },
  { id: 'payments-and-subscriptions', title: 'Payments & Subscriptions' },
  { id: 'cancellation', title: 'Cancellation' },
  { id: 'intellectual-property', title: 'Intellectual Property' },
  { id: 'third-party-services', title: 'Third-Party Services' },
  { id: 'disclaimers', title: 'Disclaimers' },
  { id: 'limitation-of-liability', title: 'Limitation of Liability' },
  { id: 'termination', title: 'Termination' },
  { id: 'governing-law', title: 'Governing Law' },
  { id: 'contact', title: 'Contact Information' },
];

export default function TermsPage({ onNavigate, onOpenWorkspace }) {
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
      currentPath="/terms"
      title="Terms of Service"
      description="These Terms of Service govern your access to and use of Merchlayer’s unified commerce integration platform, developer APIs, schema tools, and associated services."
      lastUpdated="[LAST UPDATED DATE]"
      tocItems={TOC_ITEMS}
      onNavigate={onNavigate}
      onOpenWorkspace={onOpenWorkspace}
    >
      {/* 1. Acceptance of Terms */}
      <LegalSection id="acceptance-of-terms" number="01" title="Acceptance of Terms">
        <p>
          By creating an account, accessing, or utilizing the services provided by{' '}
          <span className="legal-placeholder">[LEGAL COMPANY NAME]</span> (&ldquo;<strong>Merchlayer</strong>&rdquo;, &ldquo;<strong>we</strong>&rdquo;, &ldquo;<strong>us</strong>&rdquo;, or &ldquo;<strong>our</strong>&rdquo;), you (&ldquo;<strong>Customer</strong>&rdquo; or &ldquo;<strong>User</strong>&rdquo;) agree to be legally bound by these Terms of Service (&ldquo;<strong>Terms</strong>&rdquo;).
        </p>
        <p>
          If you are entering into these Terms on behalf of a company, organization, or another legal entity, you represent and warrant that you possess the requisite legal authority to bind such entity to these Terms. If you do not agree with any part of these Terms, you must not access or use the Merchlayer platform.
        </p>
        <div className="legal-callout legal-callout--info">
          <div className="legal-callout__title">Related Agreements</div>
          Your use of the platform is also governed by our{' '}
          <a href="/privacy" className="legal-link" onClick={(e) => handleLegalLink(e, '/privacy')}>
            Privacy Policy
          </a>
          , our{' '}
          <a href="/dpa" className="legal-link" onClick={(e) => handleLegalLink(e, '/dpa')}>
            Data Processing Agreement (DPA)
          </a>
          , and our{' '}
          <a href="/cookies" className="legal-link" onClick={(e) => handleLegalLink(e, '/cookies')}>
            Cookie Policy
          </a>
          , each of which is incorporated herein by reference.
        </div>
      </LegalSection>

      {/* 2. Account Registration */}
      <LegalSection id="account-registration" number="02" title="Account Registration">
        <p>
          To access the Merchlayer platform and configure store connectors, you must register for an account. When registering, you agree to:
        </p>
        <ul>
          <li>Provide accurate, current, and complete account information as prompted during registration.</li>
          <li>Maintain and promptly update your account information to keep it accurate, current, and complete.</li>
          <li>Maintain the strict confidentiality and security of your account credentials, API tokens, and access keys.</li>
          <li>Promptly notify Merchlayer at <span className="legal-placeholder">[SUPPORT EMAIL]</span> upon discovering any unauthorized access or security compromise of your account.</li>
        </ul>
        <p>
          You are responsible for all activities, queries, and automated data pipelines initiated through your account or using your API keys.
        </p>
      </LegalSection>

      {/* 3. Use of Merchlayer */}
      <LegalSection id="use-of-merchlayer" number="03" title="Use of Merchlayer">
        <p>
          Merchlayer provides a unified commerce data layer enabling businesses to authenticate commerce platforms, extract data resources (including orders, inventory, products, customers, fulfillments, and payments), normalize datasets into consistent schemas, and route structured data to external analytics, databases, and AI workflows.
        </p>
        <p>
          Subject to full compliance with these Terms, Merchlayer grants you a limited, non-exclusive, non-transferable, revocable license to access and use the platform strictly for your internal business operations.
        </p>
        <h3>API Access & Rate Limits</h3>
        <p>
          We may implement reasonable technical rate limits, query concurrency caps, and payload thresholds to safeguard platform stability and prevent system disruption. You agree not to bypass or attempt to circumvent these limitations.
        </p>
      </LegalSection>

      {/* 4. Shopify and Amazon Integrations */}
      <LegalSection id="shopify-amazon-integrations" number="04" title="Shopify and Amazon Integrations">
        <p>
          Merchlayer allows you to connect supported third-party e-commerce stores and marketplaces, including Shopify, Amazon, WooCommerce, Adobe Commerce, and custom REST/GraphQL endpoints.
        </p>
        <ul>
          <li>
            <strong>Authorization:</strong> When connecting a store, you authorize Merchlayer to authenticate via OAuth tokens, API keys, or seller credentials, and to read, extract, normalize, and sync designated commerce records in accordance with your configuration.
          </li>
          <li>
            <strong>Third-Party Terms Compliance:</strong> You remain solely responsible for complying with all applicable terms, developer rules, and acceptable use policies imposed by third-party platforms (such as the Shopify API License and Terms of Use, and Amazon Marketplace Developer Policies).
          </li>
          <li>
            <strong>Multi-Store Scope:</strong> You warrant that you possess all necessary merchant permissions, ownership rights, or client consents required to connect each individual store domain or marketplace identifier.
          </li>
        </ul>
      </LegalSection>

      {/* 5. Acceptable Use */}
      <LegalSection id="acceptable-use" number="05" title="Acceptable Use">
        <p>You agree not to engage in, attempt to engage in, or assist others in any of the following prohibited actions:</p>
        <ul>
          <li>Reverse engineering, decompiling, disassembling, or extracting the source code or underlying schemas of the platform.</li>
          <li>Using the service to transmit malicious software, viruses, worms, or destructive code.</li>
          <li>Interfering with, disrupting, or compromising the integrity, performance, or availability of Merchlayer servers, networks, or connected endpoints.</li>
          <li>Harvesting, scraping, or mining data from the platform without explicit authorization.</li>
          <li>Reselling, sublicensing, timesharing, or providing white-label commercial access to the platform without prior written agreement.</li>
          <li>Using Merchlayer in violation of any applicable local, state, national, or international privacy and data protection laws.</li>
        </ul>
      </LegalSection>

      {/* 6. Payments and Subscriptions */}
      <LegalSection id="payments-and-subscriptions" number="06" title="Payments and Subscriptions">
        <p>
          Certain features, sync frequencies, connector tiers, and volume allowances are offered on a paid subscription basis.
        </p>
        <ul>
          <li>
            <strong>Billing Cycles:</strong> Subscription fees are billed in advance on a recurring monthly or annual basis, as selected during plan checkout.
          </li>
          <li>
            <strong>Payment Authorization:</strong> By providing payment details, you authorize Merchlayer and its payment processing partners to charge all applicable fees incurred by your account.
          </li>
          <li>
            <strong>Taxes:</strong> Fees are exclusive of applicable value-added, sales, or withholding taxes, which will be charged where legally required.
          </li>
          <li>
            <strong>Plan Adjustments:</strong> Upgrades and tier adjustments take effect immediately, with prorated billing applied as appropriate.
          </li>
        </ul>
      </LegalSection>

      {/* 7. Cancellation */}
      <LegalSection id="cancellation" number="07" title="Cancellation">
        <p>
          You may cancel your subscription at any time via your account workspace settings or by submitting a written request to <span className="legal-placeholder">[SUPPORT EMAIL]</span>.
        </p>
        <p>
          Upon cancellation, your subscription will remain active until the conclusion of your current paid billing period. No refunds or credits are issued for partial billing periods unless explicitly required by applicable law.
        </p>
        <p>
          Following plan expiration, active pipeline syncs and API keys associated with paid tiers may be paused or downgraded to free tier limits.
        </p>
      </LegalSection>

      {/* 8. Intellectual Property */}
      <LegalSection id="intellectual-property" number="08" title="Intellectual Property">
        <h3>Merchlayer IP</h3>
        <p>
          All right, title, and interest in and to the Merchlayer platform—including software, APIs, database schemas, connectors, visual designs, logos, and documentation—belong exclusively to <span className="legal-placeholder">[LEGAL COMPANY NAME]</span> and its licensors.
        </p>
        <h3>Customer Data Ownership</h3>
        <p>
          As between Customer and Merchlayer, Customer retains all ownership rights, intellectual property rights, and title in and to all raw commerce records, order logs, product catalogs, and customer data connected to or processed through the platform (&ldquo;<strong>Customer Data</strong>&rdquo;).
        </p>
        <p>
          Customer grants Merchlayer a limited, non-exclusive license to process, normalize, cache, and transmit Customer Data solely to the extent necessary to deliver and operate the platform services requested by Customer.
        </p>
      </LegalSection>

      {/* 9. Third-Party Services */}
      <LegalSection id="third-party-services" number="09" title="Third-Party Services">
        <p>
          The platform operates by interfacing with external third-party services, APIs, databases, data warehouses, and e-commerce platforms. Merchlayer does not control, endorse, or assume responsibility for the continuous availability, accuracy, API rate changes, or service interruptions of any third-party providers.
        </p>
        <p>
          Any downtime, API changes, or credential revocations initiated by external platforms are beyond the direct operational control of Merchlayer.
        </p>
      </LegalSection>

      {/* 10. Disclaimers */}
      <LegalSection id="disclaimers" number="10" title="Disclaimers">
        <div className="legal-callout legal-callout--warning">
          <div className="legal-callout__title">Important Notice</div>
          THE MERCHLAYER PLATFORM, DOCUMENTATION, CONNECTORS, AND SERVICES ARE PROVIDED ON AN &ldquo;AS IS&rdquo; AND &ldquo;AS AVAILABLE&rdquo; BASIS WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS, IMPLIED, STATUTORY, OR OTHERWISE.
        </div>
        <p>
          TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, MERCHLAYER DISCLAIMS ALL WARRANTIES, INCLUDING IMPLIED WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, TITLE, QUIET ENJOYMENT, AND NON-INFRINGEMENT.
        </p>
        <p>
          WE DO NOT WARRANT THAT THE SERVICE WILL BE UNINTERRUPTED, ERROR-FREE, SECURE, OR FREE FROM DATA SYNCHRONIZATION LATENCY, OR THAT DEFECTS WILL BE IMMEDIATELY CORRECTED.
        </p>
      </LegalSection>

      {/* 11. Limitation of Liability */}
      <LegalSection id="limitation-of-liability" number="11" title="Limitation of Liability">
        <p>
          TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, IN NO EVENT SHALL MERCHLAYER, ITS DIRECTORS, EMPLOYEES, PARTNERS, OR AGENTS BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, PUNITIVE, OR EXEMPLARY DAMAGES, INCLUDING LOSS OF PROFITS, LOSS OF REVENUE, LOSS OF COMMERCE SALES, LOSS OF DATA, LOSS OF GOODWILL, OR BUSINESS INTERRUPTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR INABILITY TO USE THE SERVICE.
        </p>
        <p>
          IN NO EVENT SHALL MERCHLAYER’S AGGREGATE LIABILITY ARISING FROM OR RELATED TO THESE TERMS EXCEED THE TOTAL AMOUNT ACTUALLY PAID BY CUSTOMER TO MERCHLAYER IN THE TWELVE (12) MONTHS IMMEDIATELY PRECEDING THE EVENT GIVING RISE TO THE CLAIM.
        </p>
      </LegalSection>

      {/* 12. Termination */}
      <LegalSection id="termination" number="12" title="Termination">
        <p>
          Either party may terminate these Terms if the other party breaches any material term and fails to cure such breach within thirty (30) days of receiving written notice.
        </p>
        <p>
          Merchlayer may suspend or terminate your access immediately if we reasonably determine that your account is engaged in security attacks, abusive API consumption, or illegal conduct.
        </p>
        <p>
          Upon termination, all licenses granted under these Terms terminate, and customer data will be purged according to our{' '}
          <a href="/data-retention" className="legal-link" onClick={(e) => handleLegalLink(e, '/data-retention')}>
            Data Retention & Deletion Policy
          </a>.
        </p>
      </LegalSection>

      {/* 13. Governing Law */}
      <LegalSection id="governing-law" number="13" title="Governing Law">
        <p>
          These Terms and any dispute or claim arising out of or in connection with them shall be governed by and construed in accordance with the laws of <span className="legal-placeholder">[LEGAL JURISDICTION — TO BE CONFIRMED]</span>, without regard to its conflict of law principles.
        </p>
        <p>
          The parties agree to submit to the exclusive jurisdiction of the competent courts located within <span className="legal-placeholder">[LEGAL JURISDICTION — TO BE CONFIRMED]</span> for the resolution of any legal proceedings.
        </p>
      </LegalSection>

      {/* 14. Contact */}
      <LegalSection id="contact" number="14" title="Contact Information">
        <p>
          For legal inquiries, contract clarification, or questions regarding these Terms, please contact our legal and support team:
        </p>
        <div className="legal-callout">
          <p>
            <strong>Entity:</strong> <span className="legal-placeholder">[LEGAL COMPANY NAME]</span>
            <br />
            <strong>Support:</strong> <span className="legal-placeholder">[SUPPORT EMAIL]</span>
            <br />
            <strong>Legal:</strong> <span className="legal-placeholder">[PRIVACY EMAIL]</span>
            <br />
            <strong>Mailing Address:</strong> <span className="legal-placeholder">[COMPANY ADDRESS]</span>
          </p>
        </div>
      </LegalSection>
    </LegalPageLayout>
  );
}
