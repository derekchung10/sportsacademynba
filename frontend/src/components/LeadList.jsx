import React, { useState, useRef, useEffect } from 'react';
import { SearchIcon, SortIcon, CheckIcon, ArrowUpIcon, ArrowDownIcon } from './Icons';
import { statusBadgeClass } from '../helpers';

const SORT_OPTIONS = [
  { key: 'updated_at', label: 'Last Updated', defaultOrder: 'desc' },
  { key: 'status', label: 'Status (Pipeline)', defaultOrder: 'asc' },
  { key: 'first_name', label: 'Name', defaultOrder: 'asc' },
  { key: 'total_interactions', label: 'Interactions', defaultOrder: 'desc' },
  { key: 'created_at', label: 'Date Added', defaultOrder: 'desc' },
];

export default function LeadList({
  leads,
  searchQuery,
  selectedCategory,
  selectedLeadId,
  onSearchChange,
  onClearFilters,
  onSelectLead,
  isDetailOpen,
  sortBy,
  sortOrder,
  onSortChange,
}) {
  const [sortOpen, setSortOpen] = useState(false);
  const sortRef = useRef(null);

  // Close sort dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (sortRef.current && !sortRef.current.contains(e.target)) {
        setSortOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const currentSort = SORT_OPTIONS.find((o) => o.key === sortBy) || SORT_OPTIONS[0];

  const handleSortSelect = (option) => {
    if (option.key === sortBy) {
      // Toggle direction on re-click
      onSortChange(option.key, sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      onSortChange(option.key, option.defaultOrder);
    }
    setSortOpen(false);
  };

  return (
    <div className={isDetailOpen ? 'lg:w-1/3' : 'w-full'}>
      {/* Search & Sort Bar */}
      <div className="bg-white rounded-xl border border-gray-200 p-3 mb-3 shadow-sm">
        <div className="flex gap-2">
          {/* Search */}
          <div className="flex-1 relative">
            <SearchIcon className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder="Search leads..."
              className="w-full pl-9 pr-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none bg-gray-50 focus:bg-white transition-colors"
            />
          </div>

          {/* Sort Button */}
          <div className="relative" ref={sortRef}>
            <button
              onClick={() => setSortOpen(!sortOpen)}
              className={`
                inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg border transition-all
                ${sortOpen
                  ? 'border-brand-300 bg-brand-50 text-brand-700'
                  : 'border-gray-200 bg-gray-50 text-gray-600 hover:bg-gray-100 hover:border-gray-300'
                }
              `}
            >
              <SortIcon className="w-4 h-4" />
              <span className="hidden sm:inline">{currentSort.label}</span>
              {sortOrder === 'asc' ? (
                <ArrowUpIcon className="w-3 h-3 opacity-60" />
              ) : (
                <ArrowDownIcon className="w-3 h-3 opacity-60" />
              )}
            </button>

            {/* Sort Dropdown */}
            {sortOpen && (
              <div className="absolute right-0 mt-1.5 w-52 bg-white rounded-xl border border-gray-200 shadow-lg z-30 overflow-hidden py-1 animate-dropdown">
                <div className="px-3 py-1.5 text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
                  Sort by
                </div>
                {SORT_OPTIONS.map((option) => {
                  const isActive = option.key === sortBy;
                  return (
                    <button
                      key={option.key}
                      onClick={() => handleSortSelect(option)}
                      className={`
                        w-full flex items-center justify-between px-3 py-2 text-sm text-left transition-colors
                        ${isActive
                          ? 'bg-brand-50 text-brand-700 font-medium'
                          : 'text-gray-700 hover:bg-gray-50'
                        }
                      `}
                    >
                      <span>{option.label}</span>
                      <div className="flex items-center gap-1">
                        {isActive && (
                          <>
                            {sortOrder === 'asc' ? (
                              <ArrowUpIcon className="w-3 h-3 text-brand-500" />
                            ) : (
                              <ArrowDownIcon className="w-3 h-3 text-brand-500" />
                            )}
                            <CheckIcon className="w-4 h-4 text-brand-600" />
                          </>
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Clear Button */}
          {(searchQuery || selectedCategory) && (
            <button
              onClick={onClearFilters}
              className="px-3 py-2 text-sm text-gray-500 hover:text-gray-700 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
            >
              Clear
            </button>
          )}
        </div>

        {/* Active sort indicator */}
        <div className="flex items-center gap-2 mt-2 text-[11px] text-gray-400">
          <span>
            Sorted by <span className="font-medium text-gray-500">{currentSort.label}</span>
            {' · '}
            {sortOrder === 'asc' ? 'ascending' : 'descending'}
          </span>
          <span className="ml-auto tabular-nums">{leads.length} {leads.length === 1 ? 'family' : 'families'}</span>
        </div>
      </div>

      {/* Lead Cards */}
      <div className="space-y-1.5">
        {leads.map((lead) => (
          <div
            key={lead.id}
            onClick={() => onSelectLead(lead.id)}
            className={`
              bg-white rounded-xl border p-3.5 cursor-pointer transition-all duration-150 fade-in
              ${selectedLeadId === lead.id
                ? 'ring-2 ring-brand-500 border-brand-300 shadow-sm'
                : 'border-gray-200 hover:border-gray-300 hover:shadow-sm'
              }
            `}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0 flex-1">
                <h3 className="font-medium text-gray-900 text-[15px] leading-tight">
                  {lead.first_name} {lead.last_name}
                </h3>
                {lead.child_name && (
                  <p className="text-xs text-gray-500 mt-0.5">{lead.child_name}</p>
                )}
              </div>
              <span
                className={`flex-shrink-0 inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold capitalize ${statusBadgeClass(
                  lead.status
                )}`}
              >
                {lead.status}
              </span>
            </div>
            <div className="mt-2 flex items-center gap-3 text-[11px] text-gray-400">
              {lead.sport && <span className="font-medium">{lead.sport}</span>}
              <span>{lead.total_interactions} interactions</span>
              {lead.updated_at && (
                <span className="ml-auto">{formatRelativeTime(lead.updated_at)}</span>
              )}
            </div>
            {lead.campaign_goal && (
              <p className="mt-1.5 text-[11px] text-gray-500 truncate leading-relaxed">{lead.campaign_goal}</p>
            )}
          </div>
        ))}
        {leads.length === 0 && (
          <div className="text-center py-12 text-gray-400">
            <div className="text-3xl mb-2">🔍</div>
            <p className="text-sm">No leads found</p>
            <p className="text-xs mt-1">Try adjusting your search or filters</p>
          </div>
        )}
      </div>
    </div>
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

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}
