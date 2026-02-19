import React, { useState, useEffect, useCallback, useRef } from 'react';
import Header from './components/Header';
import StatsBar from './components/StatsBar';
import ConversationList from './components/ConversationList';
import ChatView from './components/ChatView';
import InfoPanel from './components/InfoPanel';
import { fetchStats, fetchLeads, fetchLeadDetail, fetchNBAHistory } from './api';

/**
 * Messenger-style layout:
 *  ┌──────────────────────────────────────────────────────────┐
 *  │  Header (brand + stats)                                  │
 *  │  StatsBar (category tabs: All / Inbox / Awaiting / Enrolled) │
 *  ├──────────┬────────────────────────────┬──────────────────┤
 *  │ Sidebar  │  Chat View                 │  Info Panel      │
 *  │ (leads)  │  (messages + composer)      │  (details+NBA)   │
 *  └──────────┴────────────────────────────┴──────────────────┘
 */
export default function App() {
  const [stats, setStats] = useState({});
  const [leads, setLeads] = useState([]);
  const [selectedLead, setSelectedLead] = useState(null);
  const [nbaHistory, setNbaHistory] = useState([]);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [selectedStatus, setSelectedStatus] = useState('');
  const [showInfoPanel, setShowInfoPanel] = useState(true);
  const debounceRef = useRef(null);
  const selectedLeadIdRef = useRef(null);

  // ─── Load data ──────────────────────────────────────────────────────────────

  const loadStats = useCallback(() => {
    fetchStats()
      .then(setStats)
      .catch((e) => console.error('Failed to fetch stats', e));
  }, []);

  const loadLeads = useCallback(
    (search, category, status) => {
      fetchLeads({ search, category: category || '', status: status || '', sortBy: 'updated_at', sortOrder: 'desc' })
        .then(setLeads)
        .catch((e) => console.error('Failed to fetch leads', e));
    },
    []
  );

  // Initial load
  useEffect(() => {
    loadStats();
    loadLeads('', '', '');
  }, [loadStats, loadLeads]);

  // ─── Handlers ───────────────────────────────────────────────────────────────

  const handleSearchChange = useCallback(
    (value) => {
      setSearchQuery(value);
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        loadLeads(value, selectedCategory, selectedStatus);
      }, 300);
    },
    [selectedCategory, selectedStatus, loadLeads]
  );

  const handleFilterCategory = useCallback(
    (category) => {
      const newCat = category === null ? null : (selectedCategory === category ? null : category);
      setSelectedCategory(newCat);
      loadLeads(searchQuery, newCat, selectedStatus);
    },
    [selectedCategory, selectedStatus, searchQuery, loadLeads]
  );

  const handleFilterStatus = useCallback(
    (status) => {
      setSelectedStatus(status);
      loadLeads(searchQuery, selectedCategory, status);
    },
    [selectedCategory, searchQuery, loadLeads]
  );

  const handleSelectLead = useCallback(async (leadId) => {
    if (selectedLeadIdRef.current === leadId) return; // Already selected
    selectedLeadIdRef.current = leadId;
    setLoadingDetail(true);
    try {
      const [detail, history] = await Promise.all([
        fetchLeadDetail(leadId),
        fetchNBAHistory(leadId),
      ]);
      setSelectedLead(detail);
      setNbaHistory(history);
    } catch (e) {
      console.error('Failed to fetch lead detail', e);
    }
    setLoadingDetail(false);
  }, []);

  // Refresh current lead after sending a message
  const handleRefresh = useCallback(async () => {
    if (!selectedLeadIdRef.current) return;
    const leadId = selectedLeadIdRef.current;
    try {
      const [detail, history] = await Promise.all([
        fetchLeadDetail(leadId),
        fetchNBAHistory(leadId),
      ]);
      setSelectedLead(detail);
      setNbaHistory(history);
    } catch (e) {
      console.error('Failed to refresh lead', e);
    }
    // Also refresh stats and list
    loadStats();
    loadLeads(searchQuery, selectedCategory, selectedStatus);
  }, [searchQuery, selectedCategory, selectedStatus, loadStats, loadLeads]);

  return (
    <div className="h-screen flex flex-col bg-gray-50 overflow-hidden">
      {/* Top bar */}
      <Header stats={stats} />

      {/* Category tabs */}
      <div className="bg-white border-b border-gray-200 px-4">
        <StatsBar
          stats={stats}
          selectedCategory={selectedCategory}
          onFilterCategory={handleFilterCategory}
        />
      </div>

      {/* 3-panel layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Conversation list */}
        <div className="w-80 flex-shrink-0 border-r border-gray-200 bg-white">
          <ConversationList
            leads={leads}
            searchQuery={searchQuery}
            selectedLeadId={selectedLead?.lead?.id}
            selectedStatus={selectedStatus}
            onSearchChange={handleSearchChange}
            onFilterStatus={handleFilterStatus}
            onSelectLead={handleSelectLead}
          />
        </div>

        {/* Center: Chat view */}
        {loadingDetail ? (
          <div className="flex-1 flex items-center justify-center bg-gray-50">
            <div className="text-center text-gray-400">
              <div className="animate-spin w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full mx-auto" />
              <p className="text-sm mt-3">Loading conversation...</p>
            </div>
          </div>
        ) : (
          <ChatView
            detail={selectedLead}
            onRefresh={handleRefresh}
          />
        )}

        {/* Right: Info panel */}
        {selectedLead && showInfoPanel && (
          <InfoPanel
            detail={selectedLead}
            nbaHistory={nbaHistory}
            onClose={() => setShowInfoPanel(false)}
            onRefresh={handleRefresh}
          />
        )}
      </div>
    </div>
  );
}
