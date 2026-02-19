import React from 'react';
import { SearchIcon } from './Icons';

const STATUS_OPTIONS = [
  { value: '', label: 'All Statuses' },
  { value: 'new', label: 'New' },
  { value: 'contacted', label: 'Contacted' },
  { value: 'interested', label: 'Interested' },
  { value: 'trial', label: 'Trial' },
  { value: 'enrolled', label: 'Enrolled' },
  { value: 'active', label: 'Attending' },
  { value: 'at_risk', label: 'At Risk' },
  { value: 'inactive', label: 'Inactive' },
  { value: 'declined', label: 'Declined' },
];

/**
 * Messenger-style conversation sidebar.
 * Shows a list of leads as "conversations" with last message preview.
 * Hover reveals archive/unarchive action.
 */
export default function ConversationList({
  leads,
  searchQuery,
  selectedLeadId,
  selectedStatus,
  selectedCategory,
  sortBy,
  onSearchChange,
  onFilterStatus,
  onSortChange,
  onSelectLead,
  onArchive,
  onUnarchive,
}) {
  const isArchiveView = selectedCategory === 'archive';

  return (
    <div className="flex flex-col h-full">
      {/* Search + filters */}
      <div className="p-3 border-b border-gray-200 space-y-2">
        <div className="relative">
          <SearchIcon className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search families..."
            className="w-full pl-9 pr-3 py-2 bg-gray-100 rounded-full text-sm focus:ring-2 focus:ring-blue-500 focus:bg-white outline-none transition-colors"
          />
        </div>
        <div className="flex gap-1.5">
          <select
            value={selectedStatus}
            onChange={(e) => onFilterStatus(e.target.value)}
            className={`
              flex-1 px-2.5 py-1.5 text-xs rounded-lg border border-gray-200 bg-gray-50
              focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-colors
              appearance-none cursor-pointer
              ${selectedStatus ? 'text-gray-900 font-medium' : 'text-gray-500'}
            `}
            style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3E%3Cpath stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='m6 8 4 4 4-4'/%3E%3C/svg%3E")`, backgroundPosition: 'right 0.4rem center', backgroundRepeat: 'no-repeat', backgroundSize: '1.1em 1.1em', paddingRight: '1.6rem' }}
          >
            {STATUS_OPTIONS.map(({ value, label }) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
          <button
            onClick={() => onSortChange(sortBy === 'updated_at' ? 'nba_priority' : 'updated_at')}
            title={sortBy === 'nba_priority' ? 'Sorted by priority — click for recent' : 'Sorted by recent — click for priority'}
            className={`
              flex-shrink-0 inline-flex items-center gap-1 px-2 py-1.5 text-xs rounded-lg border transition-colors
              ${sortBy === 'nba_priority'
                ? 'border-amber-300 bg-amber-50 text-amber-700 font-medium'
                : 'border-gray-200 bg-gray-50 text-gray-500 hover:bg-gray-100'
              }
            `}
          >
            {sortBy === 'nba_priority' ? (
              <><SortPriorityIcon className="w-3.5 h-3.5" /> Priority</>
            ) : (
              <><SortRecentIcon className="w-3.5 h-3.5" /> Recent</>
            )}
          </button>
        </div>
      </div>

      {/* Conversation items */}
      <div className="flex-1 overflow-y-auto">
        {leads.map((lead) => {
          const isSelected = selectedLeadId === lead.id;
          return (
            <div
              key={lead.id}
              className={`
                group relative flex items-center gap-3 px-3 py-3 transition-colors cursor-pointer
                ${isSelected
                  ? 'bg-blue-50 border-l-2 border-blue-600'
                  : 'hover:bg-gray-50 border-l-2 border-transparent'
                }
              `}
              onClick={() => onSelectLead(lead.id)}
            >
              {/* Avatar */}
              <div className={`
                w-10 h-10 rounded-full flex items-center justify-center text-sm font-semibold flex-shrink-0
                ${isSelected ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-600'}
              `}>
                {lead.first_name?.[0]}{lead.last_name?.[0]}
              </div>

              {/* Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <span className={`text-sm font-semibold truncate ${isSelected ? 'text-blue-900' : 'text-gray-900'}`}>
                    {lead.first_name} {lead.last_name}
                  </span>
                  <div className="flex items-center gap-1.5 flex-shrink-0 ml-2 group-hover:hidden">
                    {lead.nba_priority && lead.nba_priority !== 'low' && (
                      <span className={`text-[9px] font-semibold px-1 py-px rounded ${priorityBadge(lead.nba_priority)}`}>
                        {lead.nba_priority === 'urgent' ? 'URGENT' : lead.nba_priority === 'high' ? 'HIGH' : 'MED'}
                      </span>
                    )}
                    <span className="text-[10px] text-gray-400">
                      {formatRelativeTime(lead.updated_at)}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${statusDotColor(lead.status)}`} />
                  <p className="text-xs text-gray-500 truncate">
                    {lead.child_name && `${lead.child_name} · `}
                    {lead.sport || lead.campaign_goal || `${lead.total_interactions} messages`}
                  </p>
                </div>
              </div>

              {/* Archive / Unarchive button — appears on hover */}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  if (isArchiveView) {
                    onUnarchive?.(lead.id);
                  } else {
                    onArchive?.(lead.id);
                  }
                }}
                title={isArchiveView ? 'Move to Inbox' : 'Archive'}
                className="
                  hidden group-hover:flex items-center justify-center
                  absolute right-3 top-1/2 -translate-y-1/2
                  w-7 h-7 rounded-full bg-gray-200 text-gray-500
                  hover:bg-gray-300 hover:text-gray-700
                  transition-all
                "
              >
                {isArchiveView ? (
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 15L3 9m0 0l6-6M3 9h12a6 6 0 010 12h-3" />
                  </svg>
                ) : (
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="m20.25 7.5-.625 10.632a2.25 2.25 0 0 1-2.247 2.118H6.622a2.25 2.25 0 0 1-2.247-2.118L3.75 7.5m8.25 3v6.75m0 0-3-3m3 3 3-3M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125Z" />
                  </svg>
                )}
              </button>

            </div>
          );
        })}

        {leads.length === 0 && (
          <div className="text-center py-12 text-gray-400">
            <p className="text-sm">{isArchiveView ? 'No archived conversations' : 'No families found'}</p>
          </div>
        )}
      </div>
    </div>
  );
}

function statusDotColor(status) {
  const map = {
    new: 'bg-blue-500',
    contacted: 'bg-yellow-500',
    interested: 'bg-green-500',
    trial: 'bg-purple-500',
    enrolled: 'bg-indigo-500',
    active: 'bg-emerald-600',
    at_risk: 'bg-orange-500',
    inactive: 'bg-gray-400',
    declined: 'bg-red-500',
    unresponsive: 'bg-gray-300',
  };
  return map[status] || 'bg-gray-400';
}

function priorityBadge(priority) {
  const map = {
    urgent: 'bg-red-100 text-red-700',
    high: 'bg-orange-100 text-orange-700',
    normal: 'bg-blue-50 text-blue-600',
  };
  return map[priority] || '';
}

function SortRecentIcon({ className }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
    </svg>
  );
}

function SortPriorityIcon({ className }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 4h13M3 8h9m-9 4h6m4 0l4-4m0 0l4 4m-4-4v12" />
    </svg>
  );
}

function formatRelativeTime(dateStr) {
  if (!dateStr) return '';
  const now = new Date();
  const d = new Date(dateStr);
  const diffMs = now - d;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'now';
  if (diffMins < 60) return `${diffMins}m`;
  if (diffHours < 24) return `${diffHours}h`;
  if (diffDays < 7) return `${diffDays}d`;
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}
