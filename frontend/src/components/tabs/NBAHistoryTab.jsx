import React from 'react';
import { actionBadgeClass, formatDate } from '../../helpers';

export default function NBAHistoryTab({ nbaHistory }) {
  return (
    <div className="space-y-3">
      {nbaHistory.map((nba) => (
        <div
          key={nba.id}
          className={`border rounded-lg p-3 ${
            nba.is_current ? 'border-brand-300 bg-brand-50' : 'border-gray-200'
          }`}
        >
          <div className="flex items-center gap-2 mb-1">
            <span
              className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium capitalize ${actionBadgeClass(
                nba.action
              )}`}
            >
              {nba.action}
            </span>
            {nba.channel && (
              <span className="text-xs text-gray-500 capitalize">{nba.channel}</span>
            )}
            <span
              className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs capitalize ${
                nba.is_current ? 'bg-brand-100 text-brand-700' : 'bg-gray-100 text-gray-500'
              }`}
            >
              {nba.is_current ? 'current' : nba.status}
            </span>
          </div>
          <p className="text-sm text-gray-700">{nba.reasoning}</p>
          <div className="mt-1 flex items-center gap-3 text-xs text-gray-400">
            <span>Rule: {nba.rule_name}</span>
            <span>{formatDate(nba.created_at)}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
