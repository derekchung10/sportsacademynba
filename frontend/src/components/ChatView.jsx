import React, { useState, useRef, useEffect } from 'react';
import { PhoneIcon, EmailIcon, SmsIcon, SpinnerIcon } from './Icons';
import { statusLabel } from '../helpers';
import { sendSMS, makeCall, sendEmail } from '../api';

/**
 * Messenger-style chat view.
 * Shows conversation thread as bubbles + message composer at bottom.
 */
export default function ChatView({ detail, onRefresh, showInfoPanel, onToggleInfoPanel, onArchive }) {
  const [messageText, setMessageText] = useState('');
  const [activeChannel, setActiveChannel] = useState('sms'); // sms | email
  const [emailSubject, setEmailSubject] = useState('');
  const [sending, setSending] = useState(false);
  const [calling, setCalling] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const { lead, interactions = [], current_nba } = detail || {};

  // Auto-scroll to bottom when new messages appear
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [interactions.length]);

  // Focus input when lead changes
  useEffect(() => {
    inputRef.current?.focus();
  }, [lead?.id]);

  if (!detail) {
    return (
      <div className="flex-1 flex items-center justify-center bg-gray-50">
        <div className="text-center text-gray-400">
          <div className="text-5xl mb-3">💬</div>
          <p className="text-lg font-medium">Select a family to start</p>
          <p className="text-sm mt-1">Choose from the list on the left</p>
        </div>
      </div>
    );
  }

  const handleSendSMS = async () => {
    if (!messageText.trim() || sending) return;
    setSending(true);
    try {
      await sendSMS(lead.id, messageText.trim());
      setMessageText('');
      onRefresh();
    } catch (e) {
      console.error('Failed to send SMS:', e);
    }
    setSending(false);
  };

  const handleSendEmail = async () => {
    if (!messageText.trim() || sending) return;
    setSending(true);
    try {
      await sendEmail(lead.id, emailSubject.trim(), messageText.trim());
      setMessageText('');
      setEmailSubject('');
      onRefresh();
    } catch (e) {
      console.error('Failed to send email:', e);
    }
    setSending(false);
  };

  const handleCall = async () => {
    if (calling) return;
    setCalling(true);
    try {
      await makeCall(lead.id);
      onRefresh();
    } catch (e) {
      console.error('Failed to make call:', e);
    }
    setCalling(false);
  };

  const handleSend = () => {
    if (activeChannel === 'sms') handleSendSMS();
    else handleSendEmail();
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Merge interactions + relevant system events (contact changes, status changes) into a unified timeline
  const events = (detail.events || []);
  const systemEvents = events
    .filter(e => ['contact_updated', 'status_changed'].includes(e.event_type))
    .map(e => ({ ...e, _type: 'event' }));

  const interactionItems = [...interactions].map(i => ({ ...i, _type: 'interaction' }));
  const timeline = [...interactionItems, ...systemEvents].sort(
    (a, b) => new Date(a.created_at) - new Date(b.created_at)
  );

  return (
    <div className="flex-1 flex flex-col h-full bg-white min-w-0">
      {/* Chat Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-white min-w-0">
        <div className="flex items-center gap-3 min-w-0 flex-1">
          <div className="w-9 h-9 rounded-full bg-blue-600 text-white flex items-center justify-center text-sm font-semibold flex-shrink-0">
            {lead.first_name?.[0]}{lead.last_name?.[0]}
          </div>
          <h2 className="text-sm font-semibold text-gray-900 truncate">
            {lead.first_name} {lead.last_name}
          </h2>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {/* Call button */}
          <button
            onClick={handleCall}
            disabled={calling}
            className={`
              inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-all
              ${calling
                ? 'bg-green-100 text-green-700 cursor-wait'
                : 'bg-green-600 text-white hover:bg-green-700 shadow-sm'
              }
            `}
          >
            {calling ? (
              <>
                <SpinnerIcon className="w-4 h-4" />
                Calling...
              </>
            ) : (
              <>
                <PhoneIcon className="w-4 h-4" />
                Call
              </>
            )}
          </button>

          {/* Toggle info panel */}
          {onToggleInfoPanel && (
            <button
              onClick={onToggleInfoPanel}
              title={showInfoPanel ? 'Hide details' : 'Show details'}
              className={`
                p-2 rounded-full transition-all
                ${showInfoPanel
                  ? 'bg-blue-100 text-blue-600 hover:bg-blue-200'
                  : 'text-gray-400 hover:bg-gray-100 hover:text-gray-600'
                }
              `}
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-1 bg-gray-50">
        {timeline.length === 0 && (
          <div className="text-center py-12 text-gray-400">
            <p className="text-sm">No messages yet</p>
            <p className="text-xs mt-1">Send an SMS or make a call to get started</p>
          </div>
        )}

        {timeline.map((item, idx) => {
          const prevItem = idx > 0 ? timeline[idx - 1] : null;
          const showTimestamp = !prevItem ||
            (new Date(item.created_at) - new Date(prevItem.created_at)) > 300000; // 5 min gap

          // ─── System event (contact update, status change) ───
          if (item._type === 'event') {
            return (
              <React.Fragment key={`evt-${item.id}`}>
                {showTimestamp && (
                  <div className="flex items-center justify-center py-2">
                    <span className="text-[10px] text-gray-400 bg-gray-50 px-3">
                      {formatMessageTime(item.created_at)}
                    </span>
                  </div>
                )}
                <div className="flex items-center justify-center py-1.5">
                  <span className={`
                    inline-flex items-center gap-1.5 text-[10px] font-medium px-3 py-1 rounded-full
                    ${item.event_type === 'contact_updated'
                      ? 'bg-teal-50 text-teal-700 border border-teal-200'
                      : 'bg-amber-50 text-amber-700 border border-amber-200'
                    }
                  `}>
                    {item.event_type === 'contact_updated' ? '✏️' : '🔄'} {humanizeInlineEvent(item)}
                  </span>
                </div>
              </React.Fragment>
            );
          }

          // ─── Interaction message ─────────────────────────────
          const interaction = item;
          const isOutbound = interaction.direction === 'outbound';

          return (
            <React.Fragment key={interaction.id}>
              {/* Timestamp separator */}
              {showTimestamp && (
                <div className="flex items-center justify-center py-2">
                  <span className="text-[10px] text-gray-400 bg-gray-50 px-3">
                    {formatMessageTime(interaction.created_at)}
                  </span>
                </div>
              )}

              {/* Channel indicator for non-SMS */}
              {interaction.channel !== 'sms' && (
                <div className="flex items-center justify-center py-1">
                  <span className={`
                    inline-flex items-center gap-1.5 text-[10px] font-medium px-2.5 py-0.5 rounded-full
                    ${interaction.channel === 'voice' ? 'bg-blue-100 text-blue-600' : 'bg-purple-100 text-purple-600'}
                  `}>
                    {interaction.channel === 'voice' ? (
                      <><PhoneIcon className="w-3 h-3" /> {interaction.direction === 'inbound' ? 'Incoming' : 'Outgoing'} Call {interaction.status === 'no_answer' ? '· No Answer' : interaction.status === 'voicemail' ? '· Voicemail' : `· ${interaction.duration_seconds || 0}s`}</>
                    ) : (
                      <><EmailIcon className="w-3 h-3" /> Email</>
                    )}
                  </span>
                </div>
              )}

              {/* Message bubble */}
              {interaction.transcript && (
                <div className={`flex ${isOutbound ? 'justify-end' : 'justify-start'}`}>
                  <div className={`
                    max-w-[75%] rounded-2xl px-3.5 py-2 text-sm leading-relaxed
                    ${interaction.channel === 'voice'
                      ? 'bg-white border border-gray-200 text-gray-700 rounded-xl max-w-[85%]'
                      : isOutbound
                        ? interaction.channel === 'email'
                          ? 'bg-purple-600 text-white rounded-br-md'
                          : 'bg-blue-600 text-white rounded-br-md'
                        : 'bg-white border border-gray-200 text-gray-900 rounded-bl-md'
                    }
                  `}>
                    {interaction.channel === 'voice' ? (
                      <div className="space-y-1.5">
                        <pre className="text-xs whitespace-pre-wrap font-sans leading-relaxed">{interaction.transcript}</pre>
                        {interaction.summary && (
                          <div className="pt-1.5 mt-1.5 border-t border-gray-100">
                            <span className="text-[10px] font-semibold text-gray-400 uppercase">Summary</span>
                            <p className="text-xs text-gray-600 mt-0.5">{interaction.summary}</p>
                          </div>
                        )}
                      </div>
                    ) : (
                      <p className="whitespace-pre-wrap">{interaction.transcript}</p>
                    )}

                    {!isOutbound && interaction.detected_intent && interaction.detected_intent !== 'unclear' && (
                      <div className="mt-1.5 flex items-center gap-1.5">
                        <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${sentimentBadge(interaction.sentiment)}`}>
                          {interaction.sentiment}
                        </span>
                        <span className="text-[10px] text-gray-400 capitalize">{interaction.detected_intent}</span>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </React.Fragment>
          );
        })}
        <div ref={messagesEndRef} />
      </div>

      {/* NBA Suggestion + Composer */}
      <div className="border-t border-gray-200 bg-white">
        {/* NBA Recommendation Banner */}
        {current_nba && (
          <div className={`flex items-start gap-2 px-3 pt-2.5 pb-1.5 ${
            current_nba.action === 'stop' ? 'text-red-700' : 'text-blue-700'
          }`}>
            <span className="text-sm flex-shrink-0 mt-px">{current_nba.action === 'stop' ? '🛑' : '💡'}</span>
            <div className="min-w-0 flex-1">
              <p className={`text-xs leading-relaxed ${
                current_nba.action === 'stop' ? 'text-red-700' : 'text-blue-700'
              }`}>
                {current_nba.reasoning}
              </p>
              {current_nba.action === 'stop' && onArchive && lead && (
                <div className="mt-1.5">
                  <button
                    onClick={() => onArchive(lead.id)}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-red-100 text-red-700 hover:bg-red-200 transition-colors"
                  >
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="m20.25 7.5-.625 10.632a2.25 2.25 0 0 1-2.247 2.118H6.622a2.25 2.25 0 0 1-2.247-2.118L3.75 7.5m8.25 3v6.75m0 0-3-3m3 3 3-3M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125Z" />
                    </svg>
                    Archive
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
        {/* Channel tabs */}
        <div className="flex items-center gap-1 px-3 pt-2">
          <button
            onClick={() => setActiveChannel('sms')}
            className={`
              inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium transition-all
              ${activeChannel === 'sms'
                ? 'bg-blue-100 text-blue-700'
                : 'text-gray-500 hover:bg-gray-100'
              }
            `}
          >
            <SmsIcon className="w-3 h-3" /> SMS
          </button>
          <button
            onClick={() => setActiveChannel('email')}
            className={`
              inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium transition-all
              ${activeChannel === 'email'
                ? 'bg-purple-100 text-purple-700'
                : 'text-gray-500 hover:bg-gray-100'
              }
            `}
          >
            <EmailIcon className="w-3 h-3" /> Email
          </button>
        </div>

        {/* Email subject line */}
        {activeChannel === 'email' && (
          <div className="px-3 pt-2">
            <input
              type="text"
              value={emailSubject}
              onChange={(e) => setEmailSubject(e.target.value)}
              placeholder="Subject..."
              className="w-full px-3 py-1.5 text-sm text-gray-900 border border-gray-200 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500 outline-none bg-white"
            />
          </div>
        )}

        {/* Text input */}
        <div className="flex items-end gap-2 p-3">
          <textarea
            ref={inputRef}
            value={messageText}
            onChange={(e) => setMessageText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={activeChannel === 'sms' ? 'Type an SMS...' : 'Compose email...'}
            rows={activeChannel === 'email' ? 4 : 1}
            className={`
              flex-1 resize-none px-4 py-2 bg-gray-100 text-gray-900 rounded-2xl text-sm focus:ring-2 outline-none transition-colors
              ${activeChannel === 'email'
                ? 'focus:ring-purple-500 focus:bg-white rounded-xl'
                : 'focus:ring-blue-500 focus:bg-white'
              }
            `}
          />
          <button
            onClick={handleSend}
            disabled={!messageText.trim() || sending}
            className={`
              p-2.5 rounded-full transition-all flex-shrink-0
              ${messageText.trim() && !sending
                ? activeChannel === 'email'
                  ? 'bg-purple-600 text-white hover:bg-purple-700'
                  : 'bg-blue-600 text-white hover:bg-blue-700'
                : 'bg-gray-200 text-gray-400 cursor-not-allowed'
              }
            `}
          >
            {sending ? (
              <SpinnerIcon className="w-5 h-5" />
            ) : (
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" />
              </svg>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

function formatMessageTime(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  const now = new Date();
  const diffDays = Math.floor((now - d) / 86400000);

  if (diffDays === 0) {
    return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  }
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) {
    return d.toLocaleDateString('en-US', { weekday: 'long' });
  }
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function humanizeInlineEvent(event) {
  if (event.event_type === 'status_changed' && event.payload) {
    const oldStatus = statusLabel(event.payload.old_status || '');
    const newStatus = statusLabel(event.payload.new_status || '');
    return `Status changed: ${oldStatus} → ${newStatus}`;
  }
  return event.description;
}

function sentimentBadge(sentiment) {
  const map = {
    positive: 'bg-green-100 text-green-700',
    neutral: 'bg-gray-100 text-gray-600',
    negative: 'bg-red-100 text-red-700',
  };
  return map[sentiment] || 'bg-gray-100 text-gray-600';
}

