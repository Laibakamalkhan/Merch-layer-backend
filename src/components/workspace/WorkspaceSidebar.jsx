import React, { useState, useRef, useEffect, useMemo } from 'react';
import { 
  Home, Sparkles, LayoutDashboard, Plus, Database, 
  FileText, Package, Users, Table as TableIcon, 
  Link2, Library, FolderClosed, Settings, HelpCircle, 
  ChevronDown, Check, LogOut, PanelLeftClose, PanelLeftOpen, 
  ArrowLeft, ArrowRight, BarChart2, Shield, Store, ExternalLink
} from 'lucide-react';

const DEFAULT_STORES = [
  { id: 'all', name: 'All stores', code: 'all', color: '#3B82F6', iconLetter: '📊', isAll: true },
  { id: 'shopify', name: 'Shopify Store', code: 'shopify', color: '#10B981', iconLetter: 'S' },
  { id: 'amazon', name: 'Amazon Store', code: 'amazon', color: '#F59E0B', iconLetter: 'a' },
  { id: 'ebay', name: 'eBay Store', code: 'ebay', color: '#EF4444', iconLetter: 'e' },
  { id: 'etsy', name: 'Etsy Store', code: 'etsy', color: '#F97316', iconLetter: 'E' },
  { id: 'webflow', name: 'Webflow Store', code: 'webflow', color: '#3B82F6', iconLetter: 'w' },
];

export default function WorkspaceSidebar({ 
  currentTab, 
  currentEntity = 'orders',
  onSelectTab, 
  onSelectEntity,
  onNewTask, 
  onCreateWithPrompt,
  onBackToLanding,
  isCollapsed,
  onToggleCollapse,
  userEmail,
  userProfile,
  planName = 'Growth plan',
  connectedCount = 5,
  liveConnectors = [],
  selectedStore = 'All stores',
  onSelectStore,
  onLogout,
  onOpenSettings,
  onOpenHelp
}) {
  const [isStoreMenuOpen, setIsStoreMenuOpen] = useState(false);
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);
  const storeMenuRef = useRef(null);
  const userMenuRef = useRef(null);

  // Close menus on outside click
  useEffect(() => {
    const handleOutside = (e) => {
      if (storeMenuRef.current && !storeMenuRef.current.contains(e.target)) {
        setIsStoreMenuOpen(false);
      }
      if (userMenuRef.current && !userMenuRef.current.contains(e.target)) {
        setIsUserMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleOutside);
    return () => document.removeEventListener('mousedown', handleOutside);
  }, []);

  // Compute dynamic store list by combining defaults with any live connectors
  const storeList = useMemo(() => {
    if (!liveConnectors || liveConnectors.length === 0) {
      return DEFAULT_STORES;
    }
    const list = [{ id: 'all', name: 'All stores', code: 'all', color: '#3B82F6', iconLetter: '📊', isAll: true }];
    const seenCodes = new Set();

    liveConnectors.forEach((c) => {
      const code = (c.code || c.platform_code || '').toLowerCase();
      seenCodes.add(code);
      list.push({
        id: c.id || code,
        name: c.name || `${c.platform || code} Store`,
        code: code,
        color: c.iconColor || (code === 'shopify' ? '#10B981' : code === 'amazon' ? '#F59E0B' : '#3B82F6'),
        iconLetter: (c.platform || code || 'S')[0],
      });
    });

    // Add fallback stores if not in live connectors
    DEFAULT_STORES.slice(1).forEach((st) => {
      if (!seenCodes.has(st.code) && list.length < 7) {
        list.push(st);
      }
    });

    return list;
  }, [liveConnectors]);

  // Derived user display name & initials
  const displayName = useProfileDisplayName(userProfile, userEmail);
  const userInitials = useInitials(displayName || userEmail);

  // Store selection handler
  const handleStoreClick = (store) => {
    if (onSelectStore) {
      onSelectStore(store.name);
    }
    setIsStoreMenuOpen(false);
  };

  return (
    <aside className={`workspace-sidebar ${isCollapsed ? 'workspace-sidebar--collapsed' : ''}`}>
      {/* 1. Header: Logo & Collapse Action */}
      <div className="workspace-sidebar__header">
        <div 
          className="workspace-sidebar__brand" 
          onClick={onBackToLanding} 
          role="button" 
          tabIndex={0} 
          title="Back to Merchlayer Landing"
        >
          <div className="ws-brand-icon">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <rect x="2" y="2" width="7" height="7" rx="2" fill="#3B82F6"/>
              <rect x="11" y="2" width="7" height="7" rx="2" fill="#60A5FA"/>
              <rect x="2" y="11" width="7" height="7" rx="2" fill="#2563EB"/>
              <rect x="11" y="11" width="7" height="7" rx="2" fill="#3B82F6"/>
            </svg>
          </div>
          {!isCollapsed && <span className="ws-brand-title">Merchlayer</span>}
        </div>

        <div className="workspace-sidebar__top-actions">
          <button 
            type="button" 
            className="ws-icon-action-btn"
            onClick={onToggleCollapse}
            title={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {isCollapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
          </button>
        </div>
      </div>

      {/* 2. Store Selector Pill & Dropdown (Reference Screenshot 1 & 2) */}
      <div className="workspace-sidebar__store-selector" ref={storeMenuRef}>
        <button
          type="button"
          className={`ws-store-pill ${isStoreMenuOpen ? 'ws-store-pill--open' : ''}`}
          onClick={() => setIsStoreMenuOpen((v) => !v)}
          title="Switch Active Store"
        >
          <div className="ws-store-pill__icon-box">
            <BarChart2 size={16} className="text-blue-500" />
          </div>
          {!isCollapsed && (
            <div className="ws-store-pill__info">
              <span className="ws-store-pill__name">{selectedStore}</span>
              <span className="ws-store-pill__count">{connectedCount} connected</span>
            </div>
          )}
          {!isCollapsed && (
            <ChevronDown size={14} className={`ws-store-pill__chevron ${isStoreMenuOpen ? 'open' : ''}`} />
          )}
        </button>

        {/* Store Selector Dropdown Popover */}
        {isStoreMenuOpen && !isCollapsed && (
          <div className="ws-store-dropdown-menu">
            <div className="ws-store-dropdown-header">SWITCH STORE</div>
            <div className="ws-store-dropdown-list">
              {storeList.map((st) => {
                const isSelected = selectedStore === st.name || (selectedStore === 'All stores' && st.isAll);
                return (
                  <button
                    key={st.id}
                    type="button"
                    className={`ws-store-item ${isSelected ? 'ws-store-item--selected' : ''}`}
                    onClick={() => handleStoreClick(st)}
                  >
                    <div className="ws-store-item__icon-wrap">
                      {st.isAll ? (
                        <div className="ws-store-icon-badge ws-store-icon-badge--all">
                          <BarChart2 size={14} className="text-blue-500" />
                        </div>
                      ) : (
                        <div 
                          className="ws-store-icon-badge"
                          style={{ backgroundColor: `${st.color}22`, color: st.color }}
                        >
                          <span>{st.iconLetter}</span>
                        </div>
                      )}
                    </div>
                    <span className="ws-store-item__label">{st.name}</span>
                    {isSelected && <Check size={14} className="ws-store-item__check" />}
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Main Sidebar Navigation Body (Scrollable) */}
      <div className="workspace-sidebar__scrollable-body">
        {/* Section 1: Main Navigation */}
        <div className="ws-nav-section">
          {/* Home */}
          <button 
            type="button" 
            className={`ws-nav-row ${currentTab === 'home' || (currentTab === 'chat' && !currentEntity) ? 'ws-nav-row--active' : ''}`}
            onClick={() => onSelectTab('home')}
            title="Home"
          >
            <div className="ws-nav-row__icon"><Home size={17} /></div>
            {!isCollapsed && <span className="ws-nav-row__label">Home</span>}
          </button>

          {/* Chat with Data */}
          <button 
            type="button" 
            className={`ws-nav-row ${currentTab === 'chat' ? 'ws-nav-row--active' : ''}`}
            onClick={() => onSelectTab('chat')}
            title="Chat with Data"
          >
            <div className="ws-nav-row__icon"><Sparkles size={17} /></div>
            {!isCollapsed && (
              <>
                <span className="ws-nav-row__label">Chat with Data</span>
                <span className="ws-ai-badge">AI</span>
              </>
            )}
          </button>

          {/* Dashboards */}
          <div className="ws-nav-group">
            <button 
              type="button" 
              className={`ws-nav-row ${currentTab === 'dashboards' ? 'ws-nav-row--active' : ''}`}
              onClick={() => onSelectTab('dashboards')}
              title="Dashboards"
            >
              <div className="ws-nav-row__icon"><LayoutDashboard size={17} /></div>
              {!isCollapsed && <span className="ws-nav-row__label">Dashboards</span>}
            </button>

            {/* Sub-item: + Create with Prompt */}
            {!isCollapsed && (
              <button 
                type="button" 
                className="ws-nav-sub-action"
                onClick={onCreateWithPrompt || onNewTask}
                title="Create dashboard with AI prompt"
              >
                <Plus size={13} />
                <span>Create with Prompt</span>
              </button>
            )}
          </div>
        </div>

        {/* Section 2: Data Explorer Tree Section (Screenshot 2) */}
        <div className="ws-nav-section">
          <div className="ws-tree-header">
            <div className="ws-tree-header__icon"><Database size={16} /></div>
            {!isCollapsed && <span className="ws-tree-header__title">Data Explorer</span>}
          </div>

          {!isCollapsed && (
            <div className="ws-tree-branch">
              {/* Orders */}
              <button
                type="button"
                className={`ws-tree-item ${(currentTab === 'table' && currentEntity === 'orders') || currentTab === 'orders' ? 'ws-tree-item--active' : ''}`}
                onClick={() => {
                  if (onSelectEntity) onSelectEntity('orders');
                  onSelectTab('table');
                }}
                title="Orders Table"
              >
                <FileText size={15} className="tree-leaf-icon" />
                <span>Orders</span>
              </button>

              {/* Products */}
              <button
                type="button"
                className={`ws-tree-item ${(currentTab === 'table' && currentEntity === 'products') || currentTab === 'products' ? 'ws-tree-item--active' : ''}`}
                onClick={() => {
                  if (onSelectEntity) onSelectEntity('products');
                  onSelectTab('table');
                }}
                title="Products Table"
              >
                <Package size={15} className="tree-leaf-icon" />
                <span>Products</span>
              </button>

              {/* Customers */}
              <button
                type="button"
                className={`ws-tree-item ${(currentTab === 'table' && currentEntity === 'customers') || currentTab === 'customers' ? 'ws-tree-item--active' : ''}`}
                onClick={() => {
                  if (onSelectEntity) onSelectEntity('customers');
                  onSelectTab('table');
                }}
                title="Customers Table"
              >
                <Users size={15} className="tree-leaf-icon" />
                <span>Customers</span>
              </button>
            </div>
          )}
        </div>

        {/* Section 3: Table View & Connections */}
        <div className="ws-nav-section">
          {/* Table View navigation item (Explicitly requested in requirement #4) */}
          <button 
            type="button" 
            className={`ws-nav-row ${currentTab === 'table' ? 'ws-nav-row--active' : ''}`}
            onClick={() => onSelectTab('table')}
            title="Database Table View"
          >
            <div className="ws-nav-row__icon"><TableIcon size={17} /></div>
            {!isCollapsed && (
              <>
                <span className="ws-nav-row__label">Table View</span>
                <span className="ws-nav-pill-badge">DB</span>
              </>
            )}
          </button>

          {/* Connections item (Preserved from existing) */}
          <button 
            type="button" 
            className={`ws-nav-row ${currentTab === 'connectors' ? 'ws-nav-row--active' : ''}`}
            onClick={() => onSelectTab('connectors')}
            title="Connections"
          >
            <div className="ws-nav-row__icon"><Link2 size={17} /></div>
            {!isCollapsed && (
              <>
                <span className="ws-nav-row__label">Connections</span>
                <span className="ws-count-badge">{connectedCount}</span>
              </>
            )}
          </button>
        </div>

        {/* Section 4: Preserved Existing Tabs (Library & Files) */}
        <div className="ws-nav-section">
          {/* Library */}
          <button 
            type="button" 
            className={`ws-nav-row ${currentTab === 'library' ? 'ws-nav-row--active' : ''}`}
            onClick={() => onSelectTab('library')}
            title="Library"
          >
            <div className="ws-nav-row__icon"><Library size={17} /></div>
            {!isCollapsed && (
              <>
                <span className="ws-nav-row__label">Library</span>
                <span className="ws-count-badge">4</span>
              </>
            )}
          </button>

          {/* Files */}
          <button 
            type="button" 
            className={`ws-nav-row ${currentTab === 'files' ? 'ws-nav-row--active' : ''}`}
            onClick={() => onSelectTab('files')}
            title="Files"
          >
            <div className="ws-nav-row__icon"><FolderClosed size={17} /></div>
            {!isCollapsed && (
              <>
                <span className="ws-nav-row__label">Files</span>
                <span className="ws-count-badge">4</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* 3. Bottom Section: Settings, Help & Docs, and User Profile Card */}
      <div className="workspace-sidebar__footer">
        {/* Settings */}
        <button 
          type="button" 
          className={`ws-footer-row ${currentTab === 'settings' ? 'ws-footer-row--active' : ''}`}
          onClick={onOpenSettings || (() => onSelectTab('connectors'))}
          title="Settings"
        >
          <div className="ws-footer-row__icon"><Settings size={16} /></div>
          {!isCollapsed && <span className="ws-footer-row__label">Settings</span>}
        </button>

        {/* Help & Docs */}
        <button 
          type="button" 
          className="ws-footer-row"
          onClick={onOpenHelp || (() => window.open('https://merchlayer.io/docs', '_blank'))}
          title="Help & Documentation"
        >
          <div className="ws-footer-row__icon"><HelpCircle size={16} /></div>
          {!isCollapsed && <span className="ws-footer-row__label">Help & Docs</span>}
        </button>

        {/* User / Profile Section (Reference Screenshot 1 & 2) */}
        <div className="ws-profile-card-wrap" ref={userMenuRef}>
          <div 
            className="ws-profile-card"
            onClick={() => setIsUserMenuOpen((v) => !v)}
            role="button"
            tabIndex={0}
            title="Account & Subscription"
          >
            <div className="ws-profile-avatar">{userInitials}</div>
            {!isCollapsed && (
              <div className="ws-profile-info">
                <span className="ws-profile-name">{displayName}</span>
                <span className="ws-profile-plan">{planName}</span>
              </div>
            )}
            {!isCollapsed && (
              <button 
                type="button" 
                className="ws-profile-logout-btn"
                onClick={(e) => {
                  e.stopPropagation();
                  onLogout();
                }}
                title="Sign out"
              >
                <LogOut size={15} />
              </button>
            )}
          </div>

          {/* User Options Dropdown Popover */}
          {isUserMenuOpen && !isCollapsed && (
            <div className="ws-user-dropdown-popover">
              <div className="ws-user-popover-head">
                <span className="user-popover-name">{displayName}</span>
                <span className="user-popover-email">{userEmail || 'admin@merchlayer.io'}</span>
              </div>
              <div className="ws-user-popover-divider" />
              <button 
                type="button" 
                className="ws-user-popover-item"
                onClick={() => {
                  setIsUserMenuOpen(false);
                  onSelectTab('connectors');
                }}
              >
                <Store size={14} />
                <span>Store Connections</span>
              </button>
              <button 
                type="button" 
                className="ws-user-popover-item"
                onClick={() => {
                  setIsUserMenuOpen(false);
                  onSelectTab('files');
                }}
              >
                <FolderClosed size={14} />
                <span>Uploaded Datasets</span>
              </button>
              <div className="ws-user-popover-divider" />
              <button 
                type="button" 
                className="ws-user-popover-item ws-user-popover-item--danger" 
                onClick={onLogout}
              >
                <LogOut size={14} />
                <span>Sign out</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}

// Helpers
function useProfileDisplayName(profile, email) {
  if (profile?.display_name) return profile.display_name;
  if (profile?.full_name) return profile.full_name;
  if (profile?.name) return profile.name;
  if (email) {
    const userPart = email.split('@')[0];
    return userPart.charAt(0).toUpperCase() + userPart.slice(1);
  }
  return 'Alex Morgan';
}

function useInitials(nameOrEmail) {
  if (!nameOrEmail) return 'AM';
  const parts = nameOrEmail.replace(/[@._-]/g, ' ').trim().split(/\s+/);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return nameOrEmail.slice(0, 2).toUpperCase();
}
