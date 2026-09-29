// Single place for ALL backend calls. Components never call fetch() directly.
const BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1').replace(/\/+$/, '');
const KEY = 'merchlayer.session';

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

// Supabase confirmation link se wapas aate waqt URL ke hash mein token ya error hota hai.
// Yeh function usay parse karta hai aur URL saaf kar deta hai.
export function consumeAuthCallback() {
  const raw = window.location.hash.replace(/^#/, '');
  if (!raw.includes('access_token=') && !raw.includes('error=')) return null;
  const q = new URLSearchParams(raw);
  window.history.replaceState(null, '', window.location.pathname + '#workspace');
  if (q.get('error')) {
    const expired = q.get('error_code') === 'otp_expired';
    return {
      error: expired
        ? 'Confirmation link expire ho gaya ya pehle use ho chuka hai. Neeche se dobara email mangwa lein.'
        : (q.get('error_description') || 'Email confirmation fail ho gayi.').replace(/\+/g, ' '),
    };
  }
  return { access_token: q.get('access_token'), refresh_token: q.get('refresh_token'), type: q.get('type') };
}

export const sessionStore = {
  get() { try { return JSON.parse(localStorage.getItem(KEY) || 'null'); } catch { return null; } },
  set(s) { localStorage.setItem(KEY, JSON.stringify(s)); },
  clear() { localStorage.removeItem(KEY); },
};

function formatDetail(detail, fallback) {
  if (!detail) return fallback;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((d) => `${(d.loc || []).slice(1).join('.')}: ${d.msg}`).join('; ');
  return fallback;
}

let refreshing = null;
function refreshSession() {
  const s = sessionStore.get();
  if (!s?.refresh_token) return Promise.reject(new ApiError(401, 'Session expired'));
  if (!refreshing) {
    refreshing = fetch(`${BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: s.refresh_token }),
    })
      .then(async (r) => {
        if (!r.ok) throw new ApiError(401, 'Session expired');
        const d = await r.json();
        sessionStore.set({ access_token: d.access_token, refresh_token: d.refresh_token || s.refresh_token });
      })
      .finally(() => { refreshing = null; });
  }
  return refreshing;
}

async function request(path, { method = 'GET', query, body, form, auth = true, _retry = false } = {}) {
  const url = new URL(BASE + path, window.location.origin);
  Object.entries(query || {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v);
  });

  const headers = {};
  if (!form) headers['Content-Type'] = 'application/json';
  const session = sessionStore.get();
  if (auth && session?.access_token) headers.Authorization = `Bearer ${session.access_token}`;

  let res;
  try {
    res = await fetch(url, { method, headers, body: form || (body ? JSON.stringify(body) : undefined) });
  } catch {
    throw new ApiError(0, 'Cannot reach the server. Is the backend running on port 8000?');
  }

  if (res.status === 401 && auth && !_retry) {
    try {
      await refreshSession();
      return request(path, { method, query, body, form, auth, _retry: true });
    } catch {
      sessionStore.clear();
      window.dispatchEvent(new Event('auth:expired'));
      throw new ApiError(401, 'Your session expired. Please sign in again.');
    }
  }

  if (res.status === 204) return null;
  let data = null;
  try { data = await res.json(); } catch { /* empty body */ }
  if (!res.ok) throw new ApiError(res.status, formatDetail(data?.detail, `Request failed (${res.status})`));
  return data;
}

export const api = {
  // auth
  signup: (b) => request('/auth/signup', { method: 'POST', body: b, auth: false }),
  resendConfirmation: (b) => request('/auth/resend-confirmation', { method: 'POST', body: b, auth: false }),
  login: (b) => request('/auth/login', { method: 'POST', body: b, auth: false }),
  logout: () => request('/auth/logout', { method: 'POST' }),
  // user / workspace
  me: () => request('/me'),
  createWorkspace: (b) => request('/me/workspaces', { method: 'POST', body: b }),
  // catalog
  platforms: () => request('/platforms', { auth: false }),
  models: () => request('/models'),
  // connections + sync
  connections: (tenant_id) => request('/connections', { query: { tenant_id } }),
  createConnection: (b) => request('/connections', { method: 'POST', body: b }),
  updateConnection: (id, b) => request(`/connections/${id}`, { method: 'PATCH', body: b }),
  testConnection: (id) => request(`/connections/${id}/test`, { method: 'POST' }),
  syncBackground: (b) => request('/sync/background', { method: 'POST', body: b }),
  syncTask: (id) => request(`/sync/tasks/${id}`),
  // chat
  createConversation: (b) => request('/conversations', { method: 'POST', body: b }),
  sendMessage: (id, b) => request(`/conversations/${id}/messages`, { method: 'POST', body: b }),
  // library / files / plan
  library: (tenant_id, q) => request('/library', { query: { tenant_id, q } }),
  files: (tenant_id) => request('/files', { query: { tenant_id } }),
  uploadFile: (tenant_id, file) => {
    const f = new FormData();
    f.append('tenant_id', tenant_id);
    f.append('upload', file);
    return request('/files/upload', { method: 'POST', form: f });
  },
  deleteFile: (id, tenant_id) => request(`/files/${id}`, { method: 'DELETE', query: { tenant_id } }),
  subscription: (tenant_id) => request('/subscription', { query: { tenant_id } }),
};
