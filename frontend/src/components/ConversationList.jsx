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
 */
export default function ConversationList({
  leads,
  searchQuery,
  selectedLeadId,
  selectedStatus,
  onSearchChange,
  onFilterStatus,
  onSelectLead,
}) {
  return (
    <div className="flex flex-col h-full">
      {/* Search + Status filter */}
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
        <select
          value={selectedStatus}
          onChange={(e) => onFilterStatus(e.target.value)}
          className={`
            w-full px-3 py-1.5 text-xs rounded-lg border border-gray-200 bg-gray-50
            focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-colors
            appearance-none cursor-pointer
            ${selectedStatus ? 'text-gray-900 font-medium' : 'text-gray-500'}
          `}
          style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3E%3Cpath stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='m6 8 4 4 4-4'/%3E%3C/svg%3E")`, backgroundPosition: 'right 0.5rem center', backgroundRepeat: 'no-repeat', backgroundSize: '1.25em 1.25em', paddingRight: '2rem' }}
        >
          {STATUS_OPTIONS.map(({ value, label }) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
      </div>

      {/* Conversation items */}
      <div className="flex-1 overflow-y-auto">
        {leads.map((lead) => {
          const isSelected = selectedLeadId === lead.id;
          return (
            <button
              key={lead.id}
              onClick={() => onSelectLead(lead.id)}
              className={`
                w-full flex items-center gap-3 px-3 py-3 text-left transition-colors
                ${isSelected
                  ? 'bg-blue-50 border-l-2 border-blue-600'
                  : 'hover:bg-gray-50 border-l-2 border-transparent'
                }
              `}
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
                  <span className="text-[10px] text-gray-400 flex-shrink-0 ml-2">
                    {formatRelativeTime(lead.updated_at)}
                  </span>
                </div>
                <div className="flex items-center gap-1.5 mt-0.5">
                  {/* Status dot */}
                  <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${statusDotColor(lead.status)}`} />
                  <p className="text-xs text-gray-500 truncate">
                    {lead.child_name && `${lead.child_name} · `}
                    {lead.sport || lead.campaign_goal || `${lead.total_interactions} messages`}
                  </p>
                </div>
              </div>

            </button>
          );
        })}

        {leads.length === 0 && (
          <div className="text-center py-12 text-gray-400">
            <p className="text-sm">No families found</p>
          </div>
        )}
      </div>
    </div>
  );
}

function statusDotColor(status) {
  const map = {
    // Acquisition
    new: 'bg-blue-500',
    contacted: 'bg-yellow-500',
    interested: 'bg-green-500',
    trial: 'bg-purple-500',
    // Retention
    enrolled: 'bg-indigo-500',
    active: 'bg-emerald-600',
    at_risk: 'bg-orange-500',
    inactive: 'bg-gray-400',
    // Terminal
    declined: 'bg-red-500',
    unresponsive: 'bg-gray-300',
  };
  return map[status] || 'bg-gray-400';
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
