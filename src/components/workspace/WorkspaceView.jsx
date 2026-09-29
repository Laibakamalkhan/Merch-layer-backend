import React, { useState } from 'react';
import WorkspaceSidebar from './WorkspaceSidebar';
import WorkspaceHeader from './WorkspaceHeader';
import WorkspaceChat from './WorkspaceChat';
import StoreConnectorsTab from './StoreConnectorsTab';
import LibraryTab from './LibraryTab';
import FilesTab from './FilesTab';
import UpgradeModal from './UpgradeModal';
import { useAuth } from '../../context/AuthContext';
import './WorkspaceView.css';

export default function WorkspaceView({ onBackToLanding }) {
  const { user, logout } = useAuth();
  const [currentTab, setCurrentTab] = useState('chat'); // 'chat' | 'connectors' | 'library' | 'files'
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isUpgradeModalOpen, setIsUpgradeModalOpen] = useState(false);
  const [activeStoreForChat, setActiveStoreForChat] = useState('Amazon');

  const handleNewTask = () => {
    setCurrentTab('chat');
  };

  const handleSelectStoreForChat = (storeName) => {
    setActiveStoreForChat(storeName);
    setCurrentTab('chat');
  };

  const handleResumeTask = (task) => {
    setCurrentTab('chat');
  };

  return (
    <div className="workspace-app">
      {/* Left Sidebar matching screenshot */}
      <WorkspaceSidebar 
        currentTab={currentTab}
        onSelectTab={setCurrentTab}
        onNewTask={handleNewTask}
        onBackToLanding={onBackToLanding}
        userEmail={user?.email}
        onLogout={logout}
        isCollapsed={isSidebarCollapsed}
        onToggleCollapse={() => setIsSidebarCollapsed((v) => !v)}
      />

      {/* Main Workspace Stage */}
      <div className="workspace-main">
        {/* Top Header with Free Plan | Upgrade Pill */}
        <WorkspaceHeader 
          onOpenUpgrade={() => setIsUpgradeModalOpen(true)}
          onBackToLanding={onBackToLanding}
        />

        {/* Dynamic Center Content View */}
        <div className="workspace-content-area">
          {currentTab === 'chat' && (
            <WorkspaceChat initialStore={activeStoreForChat} onLimitReached={() => setIsUpgradeModalOpen(true)} />
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
