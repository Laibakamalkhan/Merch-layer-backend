import React, { useState, useEffect, useCallback } from 'react';
import WorkspaceSidebar from './WorkspaceSidebar';
import WorkspaceHeader from './WorkspaceHeader';
import WorkspaceChat from './WorkspaceChat';
import StoreConnectorsTab from './StoreConnectorsTab';
import LibraryTab from './LibraryTab';
import FilesTab from './FilesTab';
import TableViewTab from './TableViewTab';
import UpgradeModal from './UpgradeModal';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../lib/api';
import './WorkspaceView.css';

export default function WorkspaceView({ onBackToLanding }) {
  const { user, tenantId, logout } = useAuth();
  const [currentTab, setCurrentTab] = useState('chat'); // 'chat' | 'home' | 'table' | 'dashboards' | 'connectors' | 'library' | 'files'
  const [currentEntity, setCurrentEntity] = useState('orders'); // 'orders' | 'products' | 'customers'
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isUpgradeModalOpen, setIsUpgradeModalOpen] = useState(false);
  const [selectedStore, setSelectedStore] = useState('All stores');
  const [liveConnectors, setLiveConnectors] = useState([]);
  const [connectedCount, setConnectedCount] = useState(5);
  const [planName, setPlanName] = useState('Growth plan');

  // Load tenant connections and subscription info dynamically
  const loadWorkspaceMeta = useCallback(async () => {
    if (!tenantId) return;
    try {
      const [connRes, subRes] = await Promise.allSettled([
        api.connections(tenantId),
        api.subscription(tenantId),
      ]);

      if (connRes.status === 'fulfilled' && connRes.value?.items) {
        const items = connRes.value.items;
        setLiveConnectors(items);
        const liveCount = items.filter((c) => 
          ['active', 'connected', 'healthy', 'ok'].includes(String(c.status).toLowerCase())
        ).length;
        setConnectedCount(liveCount > 0 ? liveCount : 5);
      }

      if (subRes.status === 'fulfilled' && subRes.value?.plan?.name) {
        setPlanName(`${subRes.value.plan.name} plan`);
      }
    } catch (err) {
      console.warn('Could not load workspace meta:', err);
    }
  }, [tenantId]);

  useEffect(() => {
    loadWorkspaceMeta();
  }, [loadWorkspaceMeta]);

  const handleNewTask = () => {
    setCurrentTab('chat');
  };

  const handleCreateWithPrompt = () => {
    setCurrentTab('chat');
  };

  const handleSelectStoreForChat = (storeName) => {
    setSelectedStore(storeName);
    setCurrentTab('chat');
  };

  const handleSelectEntity = (entity) => {
    setCurrentEntity(entity);
    setCurrentTab('table');
  };

  const handleSelectTab = (tab) => {
    if (tab === 'home') {
      setCurrentTab('chat');
    } else if (tab === 'dashboards') {
      setCurrentTab('chat');
    } else {
      setCurrentTab(tab);
    }
  };

  const handleResumeTask = (task) => {
    setCurrentTab('chat');
  };

  return (
    <div className="workspace-app">
      {/* Left Sidebar matching reference screenshot */}
      <WorkspaceSidebar 
        currentTab={currentTab}
        currentEntity={currentEntity}
        onSelectTab={handleSelectTab}
        onSelectEntity={handleSelectEntity}
        onNewTask={handleNewTask}
        onCreateWithPrompt={handleCreateWithPrompt}
        onBackToLanding={onBackToLanding}
        userEmail={user?.email}
        userProfile={user?.profile}
        planName={planName}
        connectedCount={connectedCount}
        liveConnectors={liveConnectors}
        selectedStore={selectedStore}
        onSelectStore={setSelectedStore}
        onLogout={logout}
        isCollapsed={isSidebarCollapsed}
        onToggleCollapse={() => setIsSidebarCollapsed((v) => !v)}
        onOpenSettings={() => setCurrentTab('connectors')}
        onOpenHelp={() => window.open('https://merchlayer.io/docs', '_blank')}
      />

      {/* Main Workspace Stage */}
      <div className="workspace-main">
        {/* Top Header with Plan | Upgrade Pill */}
        <WorkspaceHeader 
          onOpenUpgrade={() => setIsUpgradeModalOpen(true)}
          onBackToLanding={onBackToLanding}
        />

        {/* Dynamic Center Content View */}
        <div className="workspace-content-area">
          {currentTab === 'chat' && (
            <WorkspaceChat 
              initialStore={selectedStore === 'All stores' ? 'Shopify' : selectedStore.replace(/\s*Store$/i, '')} 
              onLimitReached={() => setIsUpgradeModalOpen(true)} 
            />
          )}

          {currentTab === 'table' && (
            <TableViewTab 
              initialEntity={currentEntity}
              activeStore={selectedStore}
              onOpenConnectors={() => setCurrentTab('connectors')}
            />
          )}

          {currentTab === 'connectors' && (
            <StoreConnectorsTab onSelectStoreForChat={handleSelectStoreForChat} />
          )}

          {currentTab === 'library' && (
            <LibraryTab onResumeTask={handleResumeTask} />
          )}

          {currentTab === 'files' && (
            <FilesTab />
          )}
        </div>
      </div>

      {/* Pro Plan Upgrade Modal */}
      <UpgradeModal 
        isOpen={isUpgradeModalOpen} 
        onClose={() => setIsUpgradeModalOpen(false)} 
      />
    </div>
  );
}
