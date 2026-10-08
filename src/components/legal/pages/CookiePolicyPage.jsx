import React from 'react';
import LegalPageLayout from '../LegalPageLayout';
import LegalSection from '../LegalSection';

const TOC_ITEMS = [
  { id: 'what-cookies-are', title: 'What Cookies Are' },
  { id: 'essential-cookies', title: 'Essential Cookies' },
  { id: 'functional-cookies', title: 'Functional Cookies' },
  { id: 'analytics-cookies', title: 'Analytics Cookies' },
  { id: 'marketing-tracking-cookies', title: 'Marketing & Tracking Cookies' },
  { id: 'third-party-cookies', title: 'Third-Party Cookies' },
  { id: 'cookie-duration', title: 'Cookie Duration' },
  { id: 'managing-cookie-preferences', title: 'Managing Preferences' },
  { id: 'contact', title: 'Contact Us' },
];

export default function CookiePolicyPage({ onNavigate, onOpenWorkspace }) {
  const handleOpenCookieModal = () => {
    window.dispatchEvent(new CustomEvent('open-cookie-preferences'));
  };

  return (
    <LegalPageLayout
      currentPath="/cookies"
      title="Cookie Policy"
      description="This Cookie Policy explains how Merchlayer uses cookies, local storage, and similar web technologies to provide, secure, and improve our services."
      lastUpdated="[LAST UPDATED DATE]"
      tocItems={TOC_ITEMS}
      onNavigate={onNavigate}
      onOpenWorkspace={onOpenWorkspace}
    >
      {/* 1. What Cookies Are */}
      <LegalSection id="what-cookies-are" number="01" title="What Cookies Are">
        <p>
          Cookies are small text files that websites place on your computer or mobile device when you visit. They are widely used to make websites work efficiently, provide personalized experiences, preserve authentication status, and furnish reporting data to service operators.
        </p>
        <p>
          In addition to cookies, <span className="legal-placeholder">[LEGAL COMPANY NAME]</span> (&ldquo;<strong>Merchlayer</strong>&rdquo;) may use similar client-side technologies such as browser Local Storage, Session Storage, and authorization tokens to manage session lifecycles across browser reloads.
        </p>
      </LegalSection>

      {/* 2. Essential Cookies */}
      <LegalSection id="essential-cookies" number="02" title="Essential Cookies">
        <p>
          Essential cookies and storage items are strictly necessary for the technical operation of Merchlayer. Without these items, basic functionalities such as signing into your workspace, validating API requests, and safeguarding against cross-site request forgery (CSRF) cannot function.
        </p>
        <div className="legal-table-wrapper">
          <table className="legal-table">
            <thead>
              <tr>
                <th>Cookie / Token Name</th>
                <th>Type</th>
                <th>Purpose</th>
                <th>Lifespan</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><code>sb-access-token / session_id</code></td>
                <td>First-party</td>
                <td>Maintains authenticated user session state</td>
                <td>Session / 30 days</td>
              </tr>
              <tr>
                <td><code>csrf_token</code></td>
                <td>First-party</td>
                <td>Protects against cross-site request forgery attacks</td>
                <td>Session</td>
              </tr>
              <tr>
                <td><code>merchlayer_cookie_consent_v1</code></td>
                <td>Local Storage</td>
                <td>Records your cookie preference choices</td>
                <td>12 months</td>
              </tr>
            </tbody>
          </table>
        </div>
      </LegalSection>

      {/* 3. Functional Cookies */}
      <LegalSection id="functional-cookies" number="03" title="Functional Cookies">
        <p>
          Functional cookies and local storage items enable enhanced user experience, remembering your preferences and interface customizations:
        </p>
        <ul>
          <li><strong>UI State:</strong> Remembering active sidebar views, schema inspector tab selections, and table pagination sizing.</li>
          <li><strong>Theme & Density:</strong> Preserving layout preferences between sessions.</li>
        </ul>
      </LegalSection>

      {/* 4. Analytics Cookies */}
      <LegalSection id="analytics-cookies" number="04" title="Analytics Cookies">
        <p>
          Analytics cookies gather aggregated, non-personally identifiable metrics on platform performance, page load latencies, and feature interaction frequencies. These metrics allow us to optimize system reliability and improve navigation flows.
        </p>
        <p>
          We only enable non-essential diagnostic cookies when you provide consent via our cookie banner or preference manager.
        </p>
      </LegalSection>

      {/* 5. Marketing/Tracking Cookies */}
      <LegalSection id="marketing-tracking-cookies" number="05" title="Marketing & Tracking Cookies">
        <p>
          Marketing cookies are used to assess the effectiveness of developer documentation referrals and campaign attribution. Merchlayer does not deploy third-party advertising networks or behavioral tracking networks across user workspaces.
        </p>
      </LegalSection>

      {/* 6. Third-Party Cookies */}
      <LegalSection id="third-party-cookies" number="06" title="Third-Party Cookies">
        <p>
          When you connect third-party commerce platforms (such as Shopify OAuth authorization screens or Amazon Seller Central logins), those external providers may set their own cookies on their respective domains. We do not control third-party cookies placed during third-party authentication handshakes.
        </p>
      </LegalSection>

      {/* 7. Cookie Duration */}
      <LegalSection id="cookie-duration" number="07" title="Cookie Duration">
        <p>Cookies used on our platform are classified into two lifespan types:</p>
        <ul>
          <li><strong>Session Cookies:</strong> Temporary files that expire automatically when you close your browser.</li>
          <li><strong>Persistent Cookies:</strong> Remain stored on your device until their configured expiration date (typically up to 12 months) or until you delete them manually through browser settings.</li>
        </ul>
      </LegalSection>

      {/* 8. Managing Cookie Preferences */}
      <LegalSection id="managing-cookie-preferences" number="08" title="Managing Cookie Preferences">
        <p>
          You have full control over your cookie choices. You can modify your preferences at any time by launching our interactive preference manager below:
        </p>
        <div className="legal-callout legal-callout--info">
          <div className="legal-callout__title">Interactive Settings</div>
          <p style={{ marginBottom: '12px' }}>
            Click the button below to review or update your cookie categories (Strictly Necessary, Functional, Analytics, Marketing):
          </p>
          <button
            type="button"
            className="cookie-btn cookie-btn--primary"
            onClick={handleOpenCookieModal}
          >
            Manage Cookie Preferences
          </button>
        </div>
        <p>
          In addition, most web browsers allow you to manage cookie settings through their preferences (e.g. Chrome, Firefox, Safari, Edge). Disabling essential cookies may impair platform functionality.
        </p>
      </LegalSection>

      {/* 9. Contact */}
      <LegalSection id="contact" number="09" title="Contact Us">
        <p>
          If you have questions about our use of cookies or tracking technologies, please contact our team:
        </p>
        <div className="legal-callout">
          <p>
            <strong>Entity:</strong> <span className="legal-placeholder">[LEGAL COMPANY NAME]</span>
            <br />
            <strong>Privacy Email:</strong> <span className="legal-placeholder">[PRIVACY EMAIL]</span>
            <br />
            <strong>Support Email:</strong> <span className="legal-placeholder">[SUPPORT EMAIL]</span>
            <br />
            <strong>Address:</strong> <span className="legal-placeholder">[COMPANY ADDRESS]</span>
          </p>
        </div>
      </LegalSection>
    </LegalPageLayout>
  );
}
