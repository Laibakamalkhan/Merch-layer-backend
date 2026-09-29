import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../../lib/api';
import { useAuth } from '../../context/AuthContext';
import ConnectStoreModal from './ConnectStoreModal';
import { 
  Store, CheckCircle2, AlertCircle, RefreshCw, Plus, 
  ExternalLink, ArrowUpRight, Search, Shield, Zap, Sparkles, Filter
} from 'lucide-react';

const COLORS = { shopify: '#96BF48', amazon: '#FF9900', woocommerce: '#96588A', walmart: '#0071DC', etsy: '#F56400', ebay: '#E53238' };
const LIVE = ['active', 'connected', 'healthy', 'ok'];

function ago(iso) {
  if (!iso) return 'Never';
  const m = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m} min ago`;
  if (m < 1440) return `${Math.round(m / 60)} h ago`;
  return `${Math.round(m / 1440)} d ago`;
}

export default function StoreConnectorsTab({ onSelectStoreForChat }) {
  const { tenantId } = useAuth();
  const [connectors, setConnectors] = useState([]);
  const [platformsByCode, setPlatformsByCode] = useState({});
  const [connectTarget, setConnectTarget] = useState(null); // { platform, existing }
  const [loadError, setLoadError] = useState('');

  const load = useCallback(async () => {
    try {
      setLoadError('');
      const [pl, cn] = await Promise.all([api.platforms(), api.connections(tenantId)]);
      const byCode = Object.fromEntries(pl.items.map((p) => [p.code, p]));
      setPlatformsByCode(byCode);
      const connected = cn.items.map((c) => ({
        id: c.id, name: c.name, platform: c.platform_name || c.platform_code, code: c.platform_code,
        iconColor: COLORS[c.platform_code] || '#3B82F6',
        status: LIVE.includes(String(c.status).toLowerCase()) ? 'connected' : 'disconnected',
        lastSync: ago(c.last_synced_at), activeSkuCount: 0, dailyOrders: 0, raw: c,
        health: String(c.status), region: byCode[c.platform_code]?.category || '—',
      }));
      const usedCodes = new Set(cn.items.map((c) => c.platform_code));
      const available = pl.items.filter((p) => !usedCodes.has(p.code)).map((p) => ({
        id: `avail-${p.code}`, name: p.name, platform: p.name, code: p.code,
        iconColor: COLORS[p.code] || '#3B82F6', status: 'available', lastSync: 'Never',
        activeSkuCount: 0, dailyOrders: 0, connectable: p.connectable,
        health: p.connectable ? 'Ready to connect' : 'Coming soon', region: p.category || '—',
      }));
      setConnectors([...connected, ...available]);
    } catch (err) {
      setLoadError(err.message);
    }
  }, [tenantId]);

  useEffect(() => { load(); }, [load]);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');
  const [isSyncingAll, setIsSyncingAll] = useState(false);

  const handleSyncAll = async () => {
    const ids = connectors.filter((c) => c.status === 'connected').map((c) => c.id);
    if (!ids.length) return;
    setIsSyncingAll(true);
    try {
      await api.syncBackground({ tenant_id: tenantId, connection_ids: ids, rebuild_rag_after_sync: true });
      setTimeout(load, 3000);
    } catch (err) {
      setLoadError(err.message);
    } finally {
      setIsSyncingAll(false);
    }
  };

  const filtered = connectors.filter((item) => {
    const matchesSearch = item.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
                          item.platform.toLowerCase().includes(searchQuery.toLowerCase());
    if (filterStatus === 'all') return matchesSearch;
    if (filterStatus === 'connected') return matchesSearch && item.status === 'connected';
    if (filterStatus === 'available') return matchesSearch && item.status !== 'connected';
    return matchesSearch;
  });

  return (
    <div className="workspace-connectors">
      <div className="workspace-connectors__header">
        <div>
          <h2 className="workspace-connectors__title">Store Connectors</h2>
          <p className="workspace-connectors__subtitle">
            Manage your unified commerce data pipelines, sync frequencies, and API health across all sales channels.
          </p>
        </div>
        <div className="workspace-connectors__actions">
          <button 
            className={`ws-btn ws-btn--secondary ${isSyncingAll ? 'ws-btn--loading' : ''}`}
            onClick={handleSyncAll}
          >
            <RefreshCw size={15} className={isSyncingAll ? 'spin' : ''} />
            <span>{isSyncingAll ? 'Syncing...' : 'Sync All Stores'}</span>
          </button>
          <button className="ws-btn ws-btn--primary" onClick={() => setFilterStatus('available')}>
            <Plus size={15} />
            <span>Add New Store</span>
          </button>
        </div>
      </div>

      {loadError && <p role="alert" style={{ color: '#F87171', margin: '8px 0' }}>⚠ {loadError}</p>}

      {/* Filter and Search Bar */}
      <div className="workspace-connectors__toolbar">
        <div className="workspace-search-input">
          <Search size={16} />
          <input 
            type="text" 
            placeholder="Search connectors by name or platform..." 
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        <div className="workspace-filter-pills">
          <button 
            className={`ws-filter-pill ${filterStatus === 'all' ? 'active' : ''}`}
            onClick={() => setFilterStatus('all')}
          >
            All Channels ({connectors.length})
          </button>
          <button 
            className={`ws-filter-pill ${filterStatus === 'connected' ? 'active' : ''}`}
            onClick={() => setFilterStatus('connected')}
          >
            Connected ({connectors.filter(c => c.status === 'connected').length})
          </button>
          <button 
            className={`ws-filter-pill ${filterStatus === 'available' ? 'active' : ''}`}
            onClick={() => setFilterStatus('available')}
          >
            Available ({connectors.filter(c => c.status !== 'connected').length})
          </button>
        </div>
      </div>

      {/* Grid of Connectors */}
      <div className="workspace-connectors__grid">
        {filtered.map((store) => (
          <div key={store.id} className={`store-card ${store.status === 'connected' ? 'store-card--connected' : ''}`}>
            <div className="store-card__top">
              <div className="store-card__brand">
                <div 
                  className="store-card__icon" 
                  style={{ background: `${store.iconColor}18`, borderColor: `${store.iconColor}44`, color: store.iconColor }}
                >
                  <Store size={20} />
                </div>
                <div>
                  <h3 className="store-card__name">{store.name}</h3>
                  <span className="store-card__platform">{store.platform} · {store.region}</span>
                </div>
              </div>

              <span className={`store-badge store-badge--${store.status}`}>
                {store.status === 'connected' ? (
                  <>
                    <span className="status-dot live" /> Live
                  </>
                ) : store.status === 'disconnected' ? (
                  <>
                    <AlertCircle size={12} /> Alert
                  </>
                ) : (
                  'Ready'
                )}
              </span>
            </div>

            <div className="store-card__stats">
              <div className="store-stat">
                <span className="store-stat__label">Active SKUs</span>
                <span className="store-stat__val">{store.activeSkuCount.toLocaleString()}</span>
              </div>
              <div className="store-stat">
                <span className="store-stat__label">Daily Orders</span>
                <span className="store-stat__val">{store.dailyOrders.toLocaleString()}</span>
              </div>
              <div className="store-stat">
                <span className="store-stat__label">Last Sync</span>
                <span className="store-stat__val">{store.lastSync}</span>
              </div>
            </div>

            <div className="store-card__bottom">
              <span className="store-health">
                <Shield size={13} /> {store.health}
              </span>

              {store.status === 'connected' ? (
                <button 
                  className="store-card__action-btn"
                  onClick={() => onSelectStoreForChat && onSelectStoreForChat(store.platform)}
                >
                  <Sparkles size={14} /> Ask AI
                </button>
              ) : (
                <button
                  className="store-card__action-btn store-card__action-btn--connect"
                  disabled={store.connectable === false}
                  onClick={() => setConnectTarget({ platform: platformsByCode[store.code], existing: store.raw || null })}
                >
                  <Plus size={14} /> {store.raw ? 'Fix / Reconnect' : 'Connect'}
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
      {connectTarget && (
        <ConnectStoreModal
          platform={connectTarget.platform}
          existing={connectTarget.existing}
          onClose={() => setConnectTarget(null)}
          onConnected={() => { setConnectTarget(null); load(); }}
        />
      )}
    </div>
  );
}