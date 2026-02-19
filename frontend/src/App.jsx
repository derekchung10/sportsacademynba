import React, { useState, useEffect, useCallback, useRef } from 'react';
import Header from './components/Header';
import StatsBar from './components/StatsBar';
import ConversationList from './components/ConversationList';
import ChatView from './components/ChatView';
import InfoPanel from './components/InfoPanel';
import { fetchStats, fetchLeads, fetchLeadDetail, fetchNBAHistory, archiveLead, unarchiveLead } from './api';

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
function ss(key, fallback) {
  try { return sessionStorage.getItem(key) ?? fallback; } catch { return fallback; }
}

export default function App() {
  const [stats, setStats] = useState({});
  const [leads, setLeads] = useState([]);
  const [selectedLead, setSelectedLead] = useState(null);
  const [nbaHistory, setNbaHistory] = useState([]);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState(() => ss('category', 'inbox'));
  const [selectedStatus, setSelectedStatus] = useState(() => ss('status', ''));
  const [sortBy, setSortBy] = useState(() => ss('sortBy', 'updated_at'));
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
    (search, category, status, sort = 'updated_at') => {
      fetchLeads({ search, category: category || '', status: status || '', sortBy: sort, sortOrder: 'desc' })
        .then(setLeads)
        .catch((e) => console.error('Failed to fetch leads', e));
    },
    []
  );

  // Initial load — restore from session or default to inbox
  useEffect(() => {
    const cat = ss('category', 'inbox');
    const status = ss('status', '');
    const sort = ss('sortBy', 'updated_at');
    const leadId = ss('selectedLeadId', '');
    loadStats();
    loadLeads('', cat, status, sort);
    if (leadId) handleSelectLead(leadId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadStats, loadLeads]);

  // ─── Handlers ───────────────────────────────────────────────────────────────

  const handleSearchChange = useCallback(
    (value) => {
      setSearchQuery(value);
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        loadLeads(value, selectedCategory, selectedStatus, sortBy);
      }, 300);
    },
    [selectedCategory, selectedStatus, sortBy, loadLeads]
  );

  const handleFilterCategory = useCallback(
    (category) => {
      setSelectedCategory(category);
      try { sessionStorage.setItem('category', category); } catch {}
      loadLeads(searchQuery, category, selectedStatus, sortBy);
    },
    [selectedStatus, searchQuery, sortBy, loadLeads]
  );

  const handleFilterStatus = useCallback(
    (status) => {
      setSelectedStatus(status);
      try { sessionStorage.setItem('status', status); } catch {}
      loadLeads(searchQuery, selectedCategory, status, sortBy);
    },
    [selectedCategory, searchQuery, sortBy, loadLeads]
  );

  const handleSortChange = useCallback(
    (newSort) => {
      setSortBy(newSort);
      try { sessionStorage.setItem('sortBy', newSort); } catch {}
      loadLeads(searchQuery, selectedCategory, selectedStatus, newSort);
    },
    [searchQuery, selectedCategory, selectedStatus, loadLeads]
  );

  const handleSelectLead = useCallback(async (leadId) => {
    if (selectedLeadIdRef.current === leadId) return;
    selectedLeadIdRef.current = leadId;
    try { sessionStorage.setItem('selectedLeadId', leadId); } catch {}
    setLoadingDetail(true);
    try {
      const [detail, history] = await Promise.all([
        fetchLeadDetail(leadId),
        fetchNBAHistory(leadId),
      ]);
      // Guard against stale responses — user may have clicked another lead
      if (selectedLeadIdRef.current !== leadId) return;
      setSelectedLead(detail);
      setNbaHistory(history);
    } catch (e) {
      console.error('Failed to fetch lead detail', e);
    }
    if (selectedLeadIdRef.current === leadId) setLoadingDetail(false);
  }, []);

  const handleArchive = useCallback(async (leadId) => {
    try {
      await archiveLead(leadId);
      if (selectedLeadIdRef.current === leadId) {
        setSelectedLead(null);
        selectedLeadIdRef.current = null;
        try { sessionStorage.removeItem('selectedLeadId'); } catch {}
      }
      loadStats();
      loadLeads(searchQuery, selectedCategory, selectedStatus, sortBy);
    } catch (e) {
      console.error('Failed to archive', e);
    }
  }, [searchQuery, selectedCategory, selectedStatus, sortBy, loadStats, loadLeads]);

  const handleUnarchive = useCallback(async (leadId) => {
    try {
      await unarchiveLead(leadId);
      loadStats();
      loadLeads(searchQuery, selectedCategory, selectedStatus, sortBy);
      if (selectedLeadIdRef.current === leadId) {
        const detail = await fetchLeadDetail(leadId);
        setSelectedLead(detail);
      }
    } catch (e) {
      console.error('Failed to unarchive', e);
    }
  }, [searchQuery, selectedCategory, selectedStatus, sortBy, loadStats, loadLeads]);

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
    loadLeads(searchQuery, selectedCategory, selectedStatus, sortBy);
  }, [searchQuery, selectedCategory, selectedStatus, sortBy, loadStats, loadLeads]);

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
        <div className="w-64 flex-shrink-0 border-r border-gray-200 bg-white">
          <ConversationList
            leads={leads}
            searchQuery={searchQuery}
            selectedLeadId={selectedLead?.lead?.id}
            selectedStatus={selectedStatus}
            selectedCategory={selectedCategory}
            sortBy={sortBy}
            onSearchChange={handleSearchChange}
            onFilterStatus={handleFilterStatus}
            onSortChange={handleSortChange}
            onSelectLead={handleSelectLead}
            onArchive={handleArchive}
            onUnarchive={handleUnarchive}
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
            showInfoPanel={showInfoPanel}
            onToggleInfoPanel={() => setShowInfoPanel(p => !p)}
            onArchive={handleArchive}
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
