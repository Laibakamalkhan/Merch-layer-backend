import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { api, sessionStore, consumeAuthCallback } from '../lib/api';

const AuthCtx = createContext(null);
export const useAuth = () => useContext(AuthCtx);

const slugify = (s) => s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 40) || 'workspace';

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [workspace, setWorkspace] = useState(null);
  const [loading, setLoading] = useState(true);
  const [authNotice, setAuthNotice] = useState(null); // { type: 'success' | 'error', text }

  // GET /me, and create the first workspace if the user has none (the "tenant_id rule").
  const loadMe = useCallback(async () => {
    const me = await api.me();
    let ws = me.workspaces?.[0];
    if (!ws) {
      const name = (me.email || 'my').split('@')[0];
      ws = await api.createWorkspace({
        name: `${name}'s workspace`,
        slug: `${slugify(name)}-${Math.random().toString(36).slice(2, 7)}`,
      });
    }
    setUser({ id: me.id, email: me.email, profile: me.profile });
    setWorkspace(ws);
  }, []);

  useEffect(() => {
    const onExpired = () => { setUser(null); setWorkspace(null); };
    window.addEventListener('auth:expired', onExpired);

    // Email confirmation link se wapas aaye hain?
    const cb = consumeAuthCallback();
    if (cb?.error) {
      setAuthNotice({ type: 'error', text: cb.error });
    } else if (cb?.access_token) {
      // Confirm ho gayi -> seedha login kar do (ya sirf message dikha do agar refresh token na ho)
      sessionStore.set({ access_token: cb.access_token, refresh_token: cb.refresh_token });
      setAuthNotice({ type: 'success', text: 'Email confirm ho gayi! Aap login ho gaye hain.' });
    }

    if (sessionStore.get()) {
      loadMe().catch(() => sessionStore.clear()).finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
    return () => window.removeEventListener('auth:expired', onExpired);
  }, [loadMe]);

  const login = async (email, password) => {
    const d = await api.login({ email, password });
    sessionStore.set({ access_token: d.access_token, refresh_token: d.refresh_token });
    await loadMe();
  };

  const signup = async (email, password, display_name) => {
    const d = await api.signup({ email, password, display_name: display_name || undefined });
    if (d.access_token) {
      sessionStore.set({ access_token: d.access_token, refresh_token: d.refresh_token });
      await loadMe();
      return { needsConfirmation: false };
    }
    return { needsConfirmation: true }; // Supabase "confirm email" is ON
  };

  const logout = async () => {
    try { await api.logout(); } catch { /* token may already be dead */ }
    sessionStore.clear();
    setUser(null);
    setWorkspace(null);
  };

  return (
    <AuthCtx.Provider value={{ user, workspace, tenantId: workspace?.id, loading, authNotice, setAuthNotice, login, signup, logout }}>
      {children}
    </AuthCtx.Provider>
  );
}
