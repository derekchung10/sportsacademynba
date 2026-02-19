export function formatDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  return d.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

export function tryParseJson(str) {
  try {
    const parsed = JSON.parse(str);
    if (Array.isArray(parsed)) return parsed.join(', ');
    return JSON.stringify(parsed, null, 2);
  } catch {
    return str;
  }
}

/**
 * Full lifecycle statuses:
 *   Acquisition: new → contacted → interested → trial → enrolled
 *   Retention:   enrolled → active → at_risk → inactive
 *   Terminal:    declined, unresponsive
 */

export function statusColor(status) {
  const map = {
    // Acquisition
    new: 'text-blue-600',
    contacted: 'text-yellow-600',
    interested: 'text-green-600',
    trial: 'text-purple-600',
    // Retention
    enrolled: 'text-indigo-600',
    active: 'text-emerald-700',
    at_risk: 'text-orange-600',
    inactive: 'text-gray-500',
    // Terminal
    declined: 'text-red-600',
    unresponsive: 'text-gray-400',
  };
  return map[status] || 'text-gray-600';
}

export function statusBadgeClass(status) {
  const map = {
    // Acquisition
    new: 'bg-blue-100 text-blue-700',
    contacted: 'bg-yellow-100 text-yellow-700',
    interested: 'bg-green-100 text-green-700',
    trial: 'bg-purple-100 text-purple-700',
    // Retention
    enrolled: 'bg-indigo-100 text-indigo-700',
    active: 'bg-emerald-100 text-emerald-700',
    at_risk: 'bg-orange-100 text-orange-700',
    inactive: 'bg-gray-100 text-gray-600',
    // Terminal
    declined: 'bg-red-100 text-red-700',
    unresponsive: 'bg-gray-100 text-gray-500',
  };
  return map[status] || 'bg-gray-100 text-gray-600';
}

/** Human-readable label for status */
export function statusLabel(status) {
  const map = {
    new: 'New',
    contacted: 'Contacted',
    interested: 'Interested',
    trial: 'Trial',
    enrolled: 'Enrolled',
    active: 'Attending',
    at_risk: 'At Risk',
    inactive: 'Inactive',
    declined: 'Declined',
    unresponsive: 'No Response',
  };
  return map[status] || status;
}

/** Human-readable label for action */
export function actionLabel(action) {
  const map = {
    call: 'Phone Call',
    sms: 'Send SMS',
    email: 'Send Email',
    wait: 'Wait',
    schedule_visit: 'Schedule Visit',
    escalate_to_human: 'Escalate',
    no_action: 'No Action Needed',
  };
  return map[action] || action;
}

/** Human-readable label for channel */
export function channelLabel(channel) {
  const map = {
    voice: 'Phone',
    sms: 'SMS',
    email: 'Email',
  };
  return map[channel] || channel;
}

/** Human-readable label for priority */
export function priorityLabel(priority) {
  const map = {
    low: 'Low',
    normal: 'Normal',
    high: 'High',
    urgent: 'Urgent',
  };
  return map[priority] || priority;
}

/** Human-readable label for NBA rule name */
export function ruleLabel(ruleName) {
  const map = {
    terminal_state: 'Terminal State',
    opted_out: 'Opted Out',
    inbound_interest: 'Inbound Interest',
    scheduling_request: 'Scheduling Request',
    requesting_info: 'Info Request',
    at_risk_reengagement: 'At-Risk Check-In',
    inactive_winback: 'Win-Back Outreach',
    inactive_cooldown: 'Cooling Down',
    active_checkin: 'Active Check-In',
    active_healthy: 'Healthy — No Action',
    enrolled_welcome: 'Welcome Message',
    financial_concern_outreach: 'Financial Concern',
    address_objections: 'Address Objections',
    engage_decision_maker: 'Decision Maker',
    sibling_opportunity: 'Sibling Opportunity',
    positive_engagement: 'Positive Follow-Up',
    considering_nudge: 'Gentle Nudge',
    objection_terminal: 'Objection — Stop',
    objection_soft_follow_up: 'Soft Follow-Up',
    channel_escalation_to_sms: 'Switch to SMS',
    channel_escalation_to_email: 'Switch to Email',
    channel_escalation_to_voice: 'Switch to Phone',
    voicemail_sms_follow_up: 'Voicemail Follow-Up',
    no_answer_retry: 'Retry After No Answer',
    cool_down: 'Cooling Down',
    new_lead_initial_outreach: 'First Contact',
    default_follow_up: 'Standard Follow-Up',
    fallback: 'Manual Review',
  };
  return map[ruleName] || ruleName?.replace(/_/g, ' ') || ruleName;
}

export function actionBadgeClass(action) {
  const map = {
    call: 'bg-blue-100 text-blue-700',
    sms: 'bg-green-100 text-green-700',
    email: 'bg-purple-100 text-purple-700',
    wait: 'bg-yellow-100 text-yellow-700',
    schedule_visit: 'bg-indigo-100 text-indigo-700',
    escalate_to_human: 'bg-red-100 text-red-700',
    no_action: 'bg-gray-100 text-gray-600',
  };
  return map[action] || 'bg-gray-100 text-gray-600';
}

export function priorityClass(priority) {
  const map = {
    low: 'bg-gray-100 text-gray-600',
    normal: 'bg-blue-100 text-blue-700',
    high: 'bg-orange-100 text-orange-700',
    urgent: 'bg-red-100 text-red-700',
  };
  return map[priority] || 'bg-gray-100 text-gray-600';
}

export function channelClass(channel) {
  const map = {
    voice: 'bg-blue-100 text-blue-700',
    sms: 'bg-green-100 text-green-700',
    email: 'bg-purple-100 text-purple-700',
  };
  return map[channel] || 'bg-gray-100 text-gray-600';
}

export function interactionStatusClass(status) {
  const map = {
    completed: 'bg-green-100 text-green-700',
    no_answer: 'bg-yellow-100 text-yellow-700',
    voicemail: 'bg-blue-100 text-blue-700',
    failed: 'bg-red-100 text-red-700',
    opted_out: 'bg-red-100 text-red-700',
  };
  return map[status] || 'bg-gray-100 text-gray-600';
}

export function sentimentColor(sentiment) {
  const map = {
    positive: 'text-green-600',
    neutral: 'text-gray-600',
    negative: 'text-red-600',
  };
  return map[sentiment] || 'text-gray-600';
}

export function eventIconClass(type) {
  const map = {
    interaction_completed: 'bg-blue-100 text-blue-600',
    status_changed: 'bg-amber-100 text-amber-600',
    nba_produced: 'bg-indigo-100 text-indigo-600',
    context_enriched: 'bg-green-100 text-green-600',
    lead_created: 'bg-purple-100 text-purple-600',
  };
  return map[type] || 'bg-gray-100 text-gray-600';
}

export function artifactTypeColor(type) {
  const map = {
    summary: 'text-blue-600',
    extracted_facts: 'text-green-600',
    detected_intent: 'text-purple-600',
    open_questions: 'text-amber-600',
  };
  return map[type] || 'text-gray-600';
}
