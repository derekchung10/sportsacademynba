const API_BASE = '/api';

export async function fetchStats() {
  const res = await fetch(`${API_BASE}/leads/stats`);
  if (!res.ok) throw new Error('Failed to fetch stats');
  return res.json();
}

export async function fetchLeads({ search = '', category = '', status = '', sortBy = 'updated_at', sortOrder = 'desc' } = {}) {
  let url = `${API_BASE}/leads/?limit=50`;
  if (search) url += `&search=${encodeURIComponent(search)}`;
  if (category) url += `&category=${category}`;
  if (status) url += `&status=${status}`;
  if (sortBy) url += `&sort_by=${sortBy}`;
  if (sortOrder) url += `&sort_order=${sortOrder}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch leads');
  return res.json();
}

export async function fetchLeadDetail(leadId) {
  const res = await fetch(`${API_BASE}/leads/${leadId}`);
  if (!res.ok) throw new Error('Failed to fetch lead detail');
  return res.json();
}

export async function fetchNBAHistory(leadId) {
  const res = await fetch(`${API_BASE}/nba/${leadId}/history`);
  if (!res.ok) throw new Error('Failed to fetch NBA history');
  return res.json();
}

// ─── Lead Update ─────────────────────────────────────────────────────────────

export async function updateLead(leadId, data) {
  const res = await fetch(`${API_BASE}/leads/${leadId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to update lead');
  return res.json();
}

// ─── Communication APIs ──────────────────────────────────────────────────────

export async function sendSMS(leadId, message) {
  const res = await fetch(`${API_BASE}/communicate/${leadId}/sms`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  });
  if (!res.ok) throw new Error('Failed to send SMS');
  return res.json();
}

export async function makeCall(leadId) {
  const res = await fetch(`${API_BASE}/communicate/${leadId}/call`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  if (!res.ok) throw new Error('Failed to make call');
  return res.json();
}

export async function sendEmail(leadId, subject, body) {
  const res = await fetch(`${API_BASE}/communicate/${leadId}/email`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ subject, body }),
  });
  if (!res.ok) throw new Error('Failed to send email');
  return res.json();
}
