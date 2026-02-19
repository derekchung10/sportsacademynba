import React from 'react';

/**
 * Category tabs for the full lifecycle.
 *
 * "All"             → everyone in the system
 * "Inbox"           → families with a call/text to make (your to-do list)
 * "Awaiting Reply"  → reached out, waiting to hear back
 * "Attending"       → actively coming to classes (the healthy ones)
 */

const CATEGORIES = [
  { key: null,              label: 'All',             countKey: null,             icon: null },
  { key: 'inbox',           label: 'Inbox',           countKey: 'inbox',          icon: '📥', color: 'blue' },
  { key: 'awaiting_reply',  label: 'Awaiting Reply',  countKey: 'awaiting_reply', icon: '⏳', color: 'amber' },
  { key: 'attending',       label: 'Attending',       countKey: 'attending',      icon: '✓',  color: 'emerald' },
];

const ACTIVE_STYLES = {
  blue:    'border-blue-600 text-blue-700',
  amber:   'border-amber-500 text-amber-700',
  emerald: 'border-emerald-600 text-emerald-700',
};

export default function StatsBar({ stats, selectedCategory, onFilterCategory }) {
  const categories = stats.leads_by_category || {};
  const total = stats.total_leads || 0;

  return (
    <div className="flex items-center gap-1 py-1">
      {CATEGORIES.map(({ key, label, countKey, icon, color }) => {
        const count = countKey ? (categories[countKey] || 0) : total;
        const isActive = selectedCategory === key;

        return (
          <button
            key={label}
            onClick={() => onFilterCategory(key)}
            className={`
              inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium
              border-b-2 transition-all -mb-px
              ${isActive
                ? color
                  ? ACTIVE_STYLES[color]
                  : 'border-gray-900 text-gray-900'
                : 'border-transparent text-gray-500 hover:text-gray-700'
              }
            `}
          >
            {icon && <span className="text-[11px]">{icon}</span>}
            {label}
            <span className={`tabular-nums text-[10px] ${isActive ? 'opacity-70' : 'text-gray-400'}`}>
              {count}
            </span>
          </button>
        );
      })}
    </div>
  );
}
