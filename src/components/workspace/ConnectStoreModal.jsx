import React, { useRef, useState } from 'react';
import { X } from 'lucide-react';
import { api } from '../../lib/api';
import { useAuth } from '../../context/AuthContext';
import './ConnectStoreModal.css';

// Builds the form from platform.connection_fields (defined by the backend manifest).
// Shopify mein in mein se sirf ek tareeqa chahiye (token YA client id+secret), isliye browser inhe zabardasti required na kare.
const SHOPIFY_CRED_KEYS = ['client_id', 'client_secret', 'access_token'];

// existing = pehle se bana hua connection (jo fail/error mein hai). Us case mein naya nahi banta, wahi update hota hai.
export default function ConnectStoreModal({ platform, existing = null, onClose, onConnected }) {
  const { tenantId } = useAuth();
  const fields = platform.connection_fields || [];
  const [name, setName] = useState(existing?.name || `${platform.name} store`);
  // Edit mode mein URL aur Client ID pehle se bhar dete hain (secret kabhi wapas nahi aata, dobara dalna parta hai)
  const [values, setValues] = useState(() => {
    const init = {};
    if (!existing) return init;
    (platform.connection_fields || []).forEach((f) => {
      if (f.type === 'secret') return;
      if (f.target === 'base_url' && existing.base_url) init[f.key] = existing.base_url;
      else if (existing.config?.[f.key]) init[f.key] = existing.config[f.key];
    });
    return init;
  });
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState('');
  const [error, setError] = useState('');
  const pendingConnId = useRef(existing?.id || null); // pehli koshish fail ho to wahi connection dobara use hota hai

  const submit = async (e) => {
    e.preventDefault();
    setError(''); setBusy(true);
    try {
      const secrets = {}; const config = {}; let base_url;
      fields.forEach((f) => {
        const v = (values[f.key] || '').trim();
        if (!v) return;
        if (f.type === 'secret') secrets[f.key] = v;
        else if (f.target === 'base_url') base_url = v;
        else config[f.key] = v;
      });

      // Edit mode mein secret khali chhod sakte hain (purana Vault mein already saved hai)
      if (!existing && platform.code === 'shopify' && !secrets.access_token && !(config.client_id && secrets.client_secret)) {
        throw new Error('Shopify ke liye ya to Access Token (shpat_...) bharein, ya Client ID + Client Secret dono.');
      }

      setStep('Saving connection…');
      let conn;
      if (pendingConnId.current) {
        conn = await api.updateConnection(pendingConnId.current, { name, base_url, config, secrets });
      } else {
        conn = await api.createConnection({
          tenant_id: tenantId, platform_code: platform.code, name, base_url, config, secrets,
        });
      }
      pendingConnId.current = conn.id;

      setStep('Testing credentials…');
      const test = await api.testConnection(conn.id);
      if (test?.ok === false || test?.success === false) throw new Error(test.message || test.error || 'Connection test failed. Check your credentials.');

      if (test?.skipped_resources?.length) setStep(test.message); // kuch resources is store par allowed nahi
      else setStep('Starting first data sync…');
      await api.syncBackground({ tenant_id: tenantId, connection_ids: [conn.id], rebuild_rag_after_sync: true });
      pendingConnId.current = null;
      onConnected();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false); setStep('');
    }
  };

  return (
    <div className="csm-overlay" onClick={busy ? undefined : onClose} role="dialog" aria-modal="true">
      <form className="csm" onClick={(e) => e.stopPropagation()} onSubmit={submit}>
        <button type="button" className="csm-close" onClick={onClose} disabled={busy} aria-label="Close"><X size={16} /></button>
        <h3>{existing ? `Reconnect ${platform.name}` : `Connect ${platform.name}`}</h3>

        <label>Connection name
          <input required value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        {fields.map((f) => (
          <label key={f.key}>{f.label || f.key}
            <input
              required={f.required !== false && !(existing && f.type === 'secret') && !(platform.code === 'shopify' && SHOPIFY_CRED_KEYS.includes(f.key))}
              type={f.type === 'secret' ? 'password' : 'text'}
              placeholder={f.placeholder || ''}
              autoComplete="off"
              value={values[f.key] || ''}
              onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))}
            />
          </label>
        ))}

        {platform.code === 'shopify' && (
          <p className="csm-step" style={{ fontSize: 12, lineHeight: 1.5 }}>
            Naye Shopify apps (2026+) mein <b>shpat_</b> token nahi milta. Shopify Dev Dashboard &gt; apna app &gt; Settings se
            <b> Client ID</b> aur <b>Client Secret</b> copy karein. Purani app ho to sirf neeche wala access token bharein.
          </p>
        )}

        {error && <p className="csm-error" role="alert">{error}</p>}
        {step && <p className="csm-step">{step}</p>}
        <button className="csm-submit" disabled={busy}>{busy ? 'Working…' : (existing ? 'Save & test again' : 'Connect')}</button>
      </form>
    </div>
  );
}