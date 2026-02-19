import React, { useState, useEffect } from 'react';
import { PhoneIcon, EmailIcon, CloseIcon, ChevronRightIcon } from './Icons';
import { statusBadgeClass, statusLabel, actionBadgeClass, actionLabel, channelLabel, priorityClass, priorityLabel, ruleLabel, formatDate } from '../helpers';
import { updateLead } from '../api';

/**
 * Right-side info panel — lead details, NBA recommendation, context, and timeline.
 * Inspired by Messenger's contact info panel.
 */
export default function InfoPanel({ detail, nbaHistory, onClose, onRefresh }) {
  const [expandedSection, setExpandedSection] = useState('nba');
  const [editingField, setEditingField] = useState(null); // 'phone' | 'email' | null
  const [editValue, setEditValue] = useState('');
  const [saving, setSaving] = useState(false);

  if (!detail) return null;

  const { lead, current_nba, events = [], context_artifacts = [] } = detail;

  const startEditing = (field) => {
    setEditingField(field);
    setEditValue(lead[field] || '');
  };

  const cancelEditing = () => {
    setEditingField(null);
    setEditValue('');
  };

  const saveField = async () => {
    if (saving) return;
    const newVal = editValue.trim();
    const oldVal = (lead[editingField] || '').trim();
    if (newVal === oldVal) { cancelEditing(); return; }
    setSaving(true);
    try {
      await updateLead(lead.id, { [editingField]: newVal || null });
      setEditingField(null);
      setEditValue('');
      if (onRefresh) onRefresh();
    } catch (e) {
      console.error('Failed to update:', e);
    }
    setSaving(false);
  };

  const handleEditKeyDown = (e) => {
    if (e.key === 'Enter') { e.preventDefault(); saveField(); }
    if (e.key === 'Escape') cancelEditing();
  };

  const toggleSection = (section) => {
    setExpandedSection(expandedSection === section ? null : section);
  };

  return (
    <div className="w-80 flex-shrink-0 border-l border-gray-200 bg-white flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-900">Details</h3>
        <button onClick={onClose} className="p-1 text-gray-400 hover:text-gray-600 rounded">
          <CloseIcon className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* Lead Profile Card */}
        <div className="p-4 text-center border-b border-gray-100">
          <div className="w-16 h-16 rounded-full bg-blue-600 text-white flex items-center justify-center text-xl font-semibold mx-auto">
            {lead.first_name?.[0]}{lead.last_name?.[0]}
          </div>
          <h2 className="mt-2 text-base font-semibold text-gray-900">
            {lead.first_name} {lead.last_name}
          </h2>
          <span className={`inline-flex items-center px-2.5 py-0.5 mt-1 rounded-full text-xs font-medium ${statusBadgeClass(lead.status)}`}>
            Status: {statusLabel(lead.status)}
          </span>

          {/* Editable Contact Info */}
          <div className="mt-3 space-y-2 text-xs w-full">
            {/* Phone */}
            <EditableContactRow
              icon={<PhoneIcon className="w-3.5 h-3.5 text-gray-400" />}
              value={lead.phone}
              placeholder="Add phone number"
              isEditing={editingField === 'phone'}
              editValue={editValue}
              saving={saving}
              onStartEdit={() => startEditing('phone')}
              onEditChange={setEditValue}
              onSave={saveField}
              onCancel={cancelEditing}
              onKeyDown={handleEditKeyDown}
            />
            {/* Email */}
            <EditableContactRow
              icon={<EmailIcon className="w-3.5 h-3.5 text-gray-400" />}
              value={lead.email}
              placeholder="Add email address"
              isEditing={editingField === 'email'}
              editValue={editValue}
              saving={saving}
              onStartEdit={() => startEditing('email')}
              onEditChange={setEditValue}
              onSave={saveField}
              onCancel={cancelEditing}
              onKeyDown={handleEditKeyDown}
              type="email"
            />
          </div>
        </div>

        {/* Quick Info */}
        <div className="px-4 py-3 border-b border-gray-100 grid grid-cols-2 gap-3 text-xs">
          <div>
            <span className="text-gray-400">Child</span>
            <p className="font-medium text-gray-900 mt-0.5">{lead.child_name || '—'}</p>
            {lead.child_age && <p className="text-gray-500">Age {lead.child_age}</p>}
          </div>
          <div>
            <span className="text-gray-400">Sport</span>
            <p className="font-medium text-gray-900 mt-0.5">{lead.sport || '—'}</p>
          </div>
          <div className="col-span-2">
            <span className="text-gray-400">Campaign</span>
            <p className="font-medium text-gray-900 mt-0.5 leading-snug break-words">{lead.campaign_goal || '—'}</p>
          </div>
        </div>

        {/* NBA Recommendation */}
        <CollapsibleSection
          title="💡 Recommended Action"
          isOpen={expandedSection === 'nba'}
          onToggle={() => toggleSection('nba')}
          highlight
        >
          {current_nba ? (
            <div className="space-y-2">
              <div className="flex items-center gap-2 flex-wrap">
                <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${actionBadgeClass(current_nba.action)}`}>
                  {actionLabel(current_nba.action)}
                </span>
                {current_nba.channel && (
                  <span className="text-xs text-gray-500">via {channelLabel(current_nba.channel)}</span>
                )}
                <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${priorityClass(current_nba.priority)}`}>
                  {priorityLabel(current_nba.priority)} Priority
                </span>
              </div>
              <p className="text-xs text-gray-700 leading-relaxed break-words">{current_nba.reasoning}</p>
              <div className="text-[10px] text-gray-400 space-y-0.5">
                {current_nba.scheduled_for && <p>Scheduled for: {formatDate(current_nba.scheduled_for)}</p>}
                {current_nba.created_at && <p>Generated: {formatDate(current_nba.created_at)}</p>}
              </div>
            </div>
          ) : (
            <p className="text-xs text-gray-400">No recommendation yet</p>
          )}
        </CollapsibleSection>

        {/* Context / Insights */}
        <CollapsibleSection
          title="🧠 Insights"
          isOpen={expandedSection === 'context'}
          onToggle={() => toggleSection('context')}
        >
          {context_artifacts.length > 0 ? (
            <div className="space-y-2">
              {context_artifacts.map((artifact) => (
                <div key={artifact.id} className="text-xs">
                  <span className="font-medium text-gray-600 capitalize">
                    {artifact.artifact_type.replace(/_/g, ' ')}
                  </span>
                  <p className="text-gray-500 mt-0.5 leading-relaxed">
                    {typeof artifact.content === 'string'
                      ? artifact.content
                      : JSON.stringify(artifact.content, null, 2)
                    }
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-gray-400">No insights yet — start a conversation</p>
          )}
        </CollapsibleSection>

        {/* Recent Activity */}
        <CollapsibleSection
          title="📋 Activity"
          isOpen={expandedSection === 'activity'}
          onToggle={() => toggleSection('activity')}
        >
          {events.length > 0 ? (
            <div className="space-y-2">
              {events.slice(0, 10).map((event) => (
                <div key={event.id} className="flex items-start gap-2 text-xs">
                  <div className={`w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0 ${eventDotColor(event.event_type)}`} />
                  <div className="min-w-0 flex-1">
                    <p className="text-gray-700 leading-snug">{humanizeEventDescription(event)}</p>
                    <p className="text-[10px] text-gray-400 mt-0.5">{formatDate(event.created_at)}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-gray-400">No activity yet</p>
          )}
        </CollapsibleSection>

        {/* NBA History */}
        {nbaHistory && nbaHistory.length > 1 && (
          <CollapsibleSection
            title="📊 Action History"
            isOpen={expandedSection === 'nba_history'}
            onToggle={() => toggleSection('nba_history')}
          >
            <div className="space-y-2">
              {nbaHistory.slice(0, 8).map((nba) => (
                <div key={nba.id} className="text-xs border-l-2 border-gray-200 pl-2">
                  <div className="flex items-center gap-1.5">
                    <span className={`font-medium ${nba.is_current ? 'text-blue-600' : 'text-gray-600'}`}>
                      {actionLabel(nba.action)}
                    </span>
                    {nba.channel && <span className="text-gray-400">via {channelLabel(nba.channel)}</span>}
                    {nba.is_current && <span className="text-[10px] bg-blue-100 text-blue-600 px-1 rounded">current</span>}
                  </div>
                  <p className="text-gray-400 mt-0.5 truncate">{nba.reasoning}</p>
                  <p className="text-[10px] text-gray-300 mt-0.5">{formatDate(nba.created_at)}</p>
                </div>
              ))}
            </div>
          </CollapsibleSection>
        )}
      </div>
    </div>
  );
}

function CollapsibleSection({ title, isOpen, onToggle, highlight, children }) {
  return (
    <div className={`border-b border-gray-100 ${highlight && isOpen ? 'bg-blue-50/50' : ''}`}>
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between px-4 py-3 text-xs font-semibold text-gray-600 hover:bg-gray-50 transition-colors"
      >
        <span>{title}</span>
        <ChevronRightIcon className={`w-3.5 h-3.5 transition-transform ${isOpen ? 'rotate-90' : ''}`} />
      </button>
      {isOpen && (
        <div className="px-4 pb-3 overflow-hidden break-words">
          {children}
        </div>
      )}
    </div>
  );
}

function EditableContactRow({
  icon, value, placeholder, isEditing, editValue, saving,
  onStartEdit, onEditChange, onSave, onCancel, onKeyDown, type = 'text',
}) {
  if (isEditing) {
    return (
      <div className="flex items-center gap-2 px-2">
        {icon}
        <input
          type={type}
          value={editValue}
          onChange={(e) => onEditChange(e.target.value)}
          onKeyDown={onKeyDown}
          autoFocus
          className="flex-1 px-2 py-1 text-xs border border-blue-300 rounded-md focus:ring-2 focus:ring-blue-500 outline-none bg-white"
          placeholder={placeholder}
        />
        <button onClick={onSave} disabled={saving} className="text-blue-600 hover:text-blue-800 text-[10px] font-semibold">
          {saving ? '...' : 'Save'}
        </button>
        <button onClick={onCancel} className="text-gray-400 hover:text-gray-600 text-[10px]">
          Cancel
        </button>
      </div>
    );
  }

  return (
    <button
      onClick={onStartEdit}
      className="flex items-center gap-2 px-2 py-1 w-full rounded-md hover:bg-gray-50 transition-colors group text-left"
    >
      {icon}
      {value ? (
        <span className="text-gray-600 flex-1 truncate">{value}</span>
      ) : (
        <span className="text-gray-300 italic flex-1">{placeholder}</span>
      )}
      <span className="text-[10px] text-gray-300 group-hover:text-blue-500 transition-colors">Edit</span>
    </button>
  );
}

function humanizeEventDescription(event) {
  // Make status_changed events human-readable
  if (event.event_type === 'status_changed' && event.payload) {
    const oldStatus = statusLabel(event.payload.old_status || '');
    const newStatus = statusLabel(event.payload.new_status || '');
    return `Status changed: ${oldStatus} → ${newStatus}`;
  }
  // Make nba_produced events human-readable
  if (event.event_type === 'nba_produced' && event.payload) {
    const action = actionLabel(event.payload.action || '');
    const channel = event.payload.channel ? ` via ${channelLabel(event.payload.channel)}` : '';
    const priority = event.payload.priority ? ` (${priorityLabel(event.payload.priority)})` : '';
    return `Recommended: ${action}${channel}${priority}`;
  }
  return event.description;
}

function eventDotColor(type) {
  const map = {
    interaction_completed: 'bg-blue-500',
    status_changed: 'bg-amber-500',
    nba_produced: 'bg-indigo-500',
    context_enriched: 'bg-green-500',
    lead_created: 'bg-purple-500',
    contact_updated: 'bg-teal-500',
  };
  return map[type] || 'bg-gray-400';
}
