import React, { useState } from 'react';
import { ArrowLeft } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../lib/api';
import './AuthPage.css';

export default function AuthPage({ onBackToLanding }) {
  const { login, signup, authNotice, setAuthNotice } = useAuth();
  const [mode, setMode] = useState('login'); // 'login' | 'signup'
  const [form, setForm] = useState({ email: '', password: '', name: '' });
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');
  const [busy, setBusy] = useState(false);

  const needsConfirm = /not confirmed/i.test(error) || /expire/i.test(authNotice?.text || '');

  const resend = async () => {
    if (!form.email.trim()) { setError('Pehle email likhein, phir "Resend" dabayein.'); return; }
    setBusy(true); setError('');
    try {
      await api.resendConfirmation({ email: form.email.trim() });
      setAuthNotice(null);
      setInfo('Naya confirmation email bhej diya gaya hai. Inbox (aur Spam) check karein.');
    } catch (err) {
      setError(err.message || 'Email dobara nahi bheja ja saka');
    } finally {
      setBusy(false);
    }
  };

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    setError(''); setInfo(''); setBusy(true);
    try {
      if (mode === 'login') {
        await login(form.email.trim(), form.password);
      } else {
        const r = await signup(form.email.trim(), form.password, form.name.trim());
        if (r.needsConfirmation) {
          setInfo('Account ban gaya! Email check karein aur confirm link par click karein.');
          setMode('login');
        }
      }
    } catch (err) {
      setError(err.message || 'Something went wrong');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={submit}>
        <button type="button" className="auth-back" onClick={onBackToLanding}>
          <ArrowLeft size={14} /> Website
        </button>
        <h1>{mode === 'login' ? 'Sign in to Merchlayer' : 'Create your account'}</h1>

        {mode === 'signup' && (
          <input placeholder="Your name" value={form.name} onChange={set('name')} autoComplete="name" />
        )}
        <input type="email" required placeholder="Email" value={form.email} onChange={set('email')} autoComplete="email" />
        <input
          type="password" required minLength={8} placeholder="Password (min 8 characters)"
          value={form.password} onChange={set('password')}
          autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
        />

        {error && <p className="auth-error" role="alert">{error}</p>}
        {info && <p className="auth-info">{info}</p>}
        {authNotice && (
          <p className={authNotice.type === 'error' ? 'auth-error' : 'auth-info'} role="status">{authNotice.text}</p>
        )}
        {needsConfirm && (
          <button type="button" className="auth-switch" onClick={resend} disabled={busy}>
            Confirmation email dobara bhejein
          </button>
        )}

        <button className="auth-submit" disabled={busy}>
          {busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Sign up'}
        </button>
        <button type="button" className="auth-switch" onClick={() => { setMode(mode === 'login' ? 'signup' : 'login'); setError(''); }}>
          {mode === 'login' ? "No account? Sign up" : 'Have an account? Sign in'}
        </button>
      </form>
    </div>
  );
}
