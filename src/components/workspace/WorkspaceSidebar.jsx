import React, { useState, useRef, useEffect } from 'react';
import { 
  Grid, Plus, Library, Clock, FileText, Search, ChevronDown, 
  PanelLeftClose, PanelLeftOpen, ArrowUpRight, Check, Settings, 
  LogOut, Store, Shield, Sparkles, ExternalLink, ArrowLeft
} from 'lucide-react';

export default function WorkspaceSidebar({ 
  currentTab, 
  onSelectTab, 
  onNewTask, 
  onBackToLanding,
  isCollapsed,
  onToggleCollapse,
  userEmail,
  onLogout
}) {
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const userMenuRef = useRef(null);

  useEffect(() => {
    const handleOutside = (e) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target)) {
        setIsUserMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleOutside);
    return () => document.removeEventListener('mousedown', handleOutside);
  }, []);

  return (
    <aside className={`workspace-sidebar ${isCollapsed ? 'workspace-sidebar--collapsed' : ''}`}>
      {/* Top Header with Logo and Action Icons */}
      <div className="workspace-sidebar__header">
        <div className="workspace-sidebar__brand" onClick={onBackToLanding} role="button" tabIndex={0} title="Back to Merchlayer Landing">
          <div className="ws-brand-icon">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <rect x="1" y="1" width="6.5" height="6.5" rx="1.5" fill="#3B82F6"/>
              <rect x="10.5" y="1" width="6.5" height="6.5" rx="1.5" fill="#60A5FA"/>
              <rect x="1" y="10.5" width="6.5" height="6.5" rx="1.5" fill="#2563EB"/>
              <rect x="10.5" y="10.5" width="6.5" height="6.5" rx="1.5" fill="#3B82F6"/>
            </svg>
          </div>
          {!isCollapsed && <span className="ws-brand-title">MERCHLAYER</span>}
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
          <button 
            type="button" 
            className="ws-icon-action-btn"
            onClick={onBackToLanding}
            title="Return to Landing Page"
          >
            <ArrowLeft size={16} />
          </button>
        </div>
      </div>

      {/* User profile dropdown pill */}
      <div className="workspace-sidebar__user-wrap" ref={userMenuRef}>
        <button 
          type="button"
          className={`ws-user-pill ${isUserMenuOpen ? 'ws-user-pill--active' : ''}`}
          onClick={() => setIsUserMenuOpen((v) => !v)}
          title="Account options"
        >
          <div className="ws-user-avatar">{(userEmail || 'U')[0].toUpperCase()}</div>
          {!isCollapsed && (
            <>
              <span className="ws-user-email">{userEmail || ''}</span>
              <ChevronDown size={14} className={`ws-user-chevron ${isUserMenuOpen ? 'open' : ''}`} />
            </>
          )}
        </button>

        {isUserMenuOpen && !isCollapsed && (
          <div className="ws-user-dropdown-menu">
            <div className="ws-user-dropdown-header">
              <span className="user-name">Store Admin</span>
              <span className="user-role">Enterprise Workspace</span>
            </div>

            <div className="ws-user-dropdown-divider" />

            <button type="button" className="ws-user-dropdown-item">
              <Store size={14} />
              <span>Switch Active Store</span>
            </button>
            <button type="button" className="ws-user-dropdown-item">
              <Settings size={14} />
              <span>API Keys & Webhooks</span>
            </button>
            <button type="button" className="ws-user-dropdown-item">
              <Shield size={14} />
              <span>Security & Audit Log</span>
            </button>

            <div className="ws-user-dropdown-divider" />

            <button type="button" className="ws-user-dropdown-item ws-user-dropdown-item--danger" onClick={onLogout}>
              <LogOut size={14} />
              <span>Sign out</span>
            </button>
          </div>
        )}
      </div>

      {/* Primary Action Button: New Task */}
      <div className="workspace-sidebar__primary-action">
        <button 
          type="button"
          className={`ws-new-task-btn ${currentTab === 'chat' ? 'ws-new-task-btn--active' : ''}`}
          onClick={onNewTask}
          title="New Task"
        >
          <div className="btn-icon">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
              <circle cx="4" cy="4" r="1.5" />
              <circle cx="12" cy="4" r="1.5" />
              <circle cx="4" cy="12" r="1.5" />
              <circle cx="12" cy="12" r="1.5" />
            </svg>
          </div>
          {!isCollapsed && <span>New Task</span>}
        </button>
      </div>

      {/* Navigation List items */}
      <nav className="workspace-sidebar__nav">
        <button 
          type="button"
          className={`ws-nav-item ${currentTab === 'library' ? 'ws-nav-item--active' : ''}`}
          onClick={() => onSelectTab('library')}
          title="Library"
        >
          <div className="ws-nav-icon">
            <Library size={18} />
          </div>
          {!isCollapsed && (
            <>
              <span className="ws-nav-label">Library</span>
              <span className="ws-nav-badge">4</span>
            </>
          )}
        </button>

        <button 
          type="button"
          className={`ws-nav-item ${currentTab === 'connectors' ? 'ws-nav-item--active' : ''}`}
          onClick={() => onSelectTab('connectors')}
          title="Store Connectors"
        >
          <div className="ws-nav-icon">
            <Clock size={18} />
          </div>
          {!isCollapsed && (
            <>
              <span className="ws-nav-label">Store Connectors</span>
              <span className="ws-nav-badge live-dot-badge">3 Live</span>
            </>
          )}
        </button>

        <button 
          type="button"
          className={`ws-nav-item ${currentTab === 'files' ? 'ws-nav-item--active' : ''}`}
          onClick={() => onSelectTab('files')}
          title="Files"
        >
          <div className="ws-nav-icon">
            <FileText size={18} />
          </div>
          {!isCollapsed && (
            <>
              <span className="ws-nav-label">Files</span>
              <span className="ws-nav-badge">4</span>
            </>
          )}
        </button>
      </nav>

      {/* Bottom Search Tasks Input */}
      <div className="workspace-sidebar__footer">
        {!isCollapsed ? (
          <div className="ws-search-tasks">
            <Search size={14} className="search-icon" />
            <input 
              type="text" 
              placeholder="Search tasks..." 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        ) : (
          <button 
            type="button" 
            className="ws-icon-action-btn"
            onClick={onToggleCollapse}
            title="Search tasks"
          >
            <Search size={16} />
          </button>
        )}
      </div>
    </aside>
  );
}
