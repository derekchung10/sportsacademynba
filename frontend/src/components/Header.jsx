import React from 'react';
import { BoltIcon, ClockIcon } from './Icons';

export default function Header({ stats }) {
  return (
    <header className="bg-white border-b border-gray-200 flex-shrink-0">
      <div className="px-4 py-2.5 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 bg-blue-600 rounded-lg flex items-center justify-center">
            <BoltIcon className="w-4 h-4 text-white" />
          </div>
          <h1 className="text-base font-semibold text-gray-900">Academy Outreach</h1>
        </div>
        <div className="flex items-center gap-3 text-sm">
          <span className="tabular-nums text-gray-400 text-xs">
            {stats.total_leads || 0} families
          </span>
          {stats.pending_scheduled_actions > 0 && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 text-[11px] font-medium">
              <ClockIcon className="w-3 h-3" />
              <span className="tabular-nums">{stats.pending_scheduled_actions} due</span>
            </span>
          )}

          {/* Logged-in user avatar */}
          <div className="flex items-center gap-2 ml-2 pl-3 border-l border-gray-200">
            <div className="w-7 h-7 rounded-full bg-gray-700 text-white flex items-center justify-center text-[11px] font-semibold cursor-default" title="Coach Davis">
              CD
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
