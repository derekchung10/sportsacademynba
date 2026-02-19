import React, { useState } from 'react';
import { PhoneIcon, EmailIcon, CloseIcon, ChevronRightIcon, SpinnerIcon } from './Icons';
import TimelineTab from './tabs/TimelineTab';
import InteractionsTab from './tabs/InteractionsTab';
import ContextTab from './tabs/ContextTab';
import NBAHistoryTab from './tabs/NBAHistoryTab';
import {
  statusBadgeClass,
  actionBadgeClass,
  priorityClass,
  formatDate,
} from '../helpers';

const TABS = [
  { key: 'timeline', label: 'Timeline' },
  { key: 'interactions', label: 'Interactions' },
  { key: 'context', label: 'Context' },
  { key: 'nba_history', label: 'NBA History' },
];

export default function LeadDetail({ detail, nbaHistory, loading, onClose }) {
  const [activeTab, setActiveTab] = useState('timeline');

  if (loading) {
    return (
      <div className="lg:w-2/3 fade-in flex justify-center py-12">
        <SpinnerIcon className="h-8 w-8 text-brand-500" />
      </div>
    );
  }

  if (!detail) return null;

  const { lead, current_nba, events, interactions, context_artifacts } = detail;

  return (
    <div className="lg:w-2/3 fade-in">
      {/* Lead Header */}
      <div className="bg-white rounded-lg border border-gray-200 p-5 mb-4">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-xl font-semibold text-gray-900">
              {lead.first_name} {lead.last_name}
            </h2>
            <div className="mt-1 flex items-center gap-4 text-sm text-gray-500">
              {lead.phone && (
                <span className="flex items-center gap-1">
                  <PhoneIcon className="w-4 h-4" />
                  <span>{lead.phone}</span>
                </span>
              )}
              {lead.email && (
                <span className="flex items-center gap-1">
                  <EmailIcon className="w-4 h-4" />
                  <span>{lead.email}</span>
                </span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span
              className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium capitalize ${statusBadgeClass(
                lead.status
              )}`}
            >
              {lead.status}
            </span>
            <button onClick={onClose} className="p-1 text-gray-400 hover:text-gray-600">
              <CloseIcon className="w-5 h-5" />
            </button>
          </div>
        </div>
        <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
          <div>
            <span className="text-gray-400 text-xs">Child</span>
            <p className="font-medium">{lead.child_name || '-'}</p>
            {lead.child_age && <p className="text-xs text-gray-500">Age {lead.child_age}</p>}
          </div>
          <div>
            <span className="text-gray-400 text-xs">Sport</span>
            <p className="font-medium">{lead.sport || '-'}</p>
          </div>
          <div>
            <span className="text-gray-400 text-xs">Interactions</span>
            <p className="font-medium">{lead.total_interactions}</p>
            <p className="text-xs text-gray-500">
              V:{lead.total_voice_attempts} S:{lead.total_sms_attempts} E:{lead.total_email_attempts}
            </p>
          </div>
          <div>
            <span className="text-gray-400 text-xs">Campaign Goal</span>
            <p className="font-medium text-xs">{lead.campaign_goal || '-'}</p>
          </div>
        </div>
      </div>

      {/* NBA Decision Card */}
      {current_nba && (
        <div className="bg-gradient-to-r from-brand-50 to-indigo-50 rounded-lg border border-brand-200 p-5 mb-4">
          <h3 className="text-sm font-semibold text-brand-800 flex items-center gap-2 mb-3">
            <ChevronRightIcon className="w-5 h-5" />
            Next Best Action
          </h3>
          <div>
            <div className="flex items-center gap-3 mb-2">
              <span
                className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm font-semibold capitalize ${actionBadgeClass(
                  current_nba.action
                )}`}
              >
                {current_nba.action}
              </span>
              {current_nba.channel && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700 capitalize">
                  {current_nba.channel}
                </span>
              )}
              <span
                className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium capitalize ${priorityClass(
                  current_nba.priority
                )}`}
              >
                {current_nba.priority} priority
              </span>
            </div>
            <p className="text-sm text-gray-700 leading-relaxed">{current_nba.reasoning}</p>
            <div className="mt-2 flex items-center gap-4 text-xs text-gray-500">
              {current_nba.rule_name && <span>Rule: {current_nba.rule_name}</span>}
              {current_nba.scheduled_for && (
                <span>Scheduled: {formatDate(current_nba.scheduled_for)}</span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <div className="border-b border-gray-200 flex">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-4 py-3 text-sm font-medium border-b-2 -mb-px ${
                activeTab === tab.key
                  ? 'border-brand-500 text-brand-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="p-4">
          {activeTab === 'timeline' && <TimelineTab events={events || []} />}
          {activeTab === 'interactions' && <InteractionsTab interactions={interactions || []} />}
          {activeTab === 'context' && <ContextTab contextArtifacts={context_artifacts} />}
          {activeTab === 'nba_history' && <NBAHistoryTab nbaHistory={nbaHistory || []} />}
        </div>
      </div>
    </div>
  );
}
