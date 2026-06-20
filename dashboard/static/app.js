const API = '/api/v1';

// ── Bootstrap ─────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', refreshAll);

async function refreshAll() {
  await Promise.all([loadStats(), loadHotLeads(), loadEscalations()]);
}

// ── Stats ─────────────────────────────────────────────────────────────

async function loadStats() {
  const data = await apiFetch('/dashboard/stats');
  if (!data) return;

  setText('stat-total',      data.total_leads);
  setText('stat-hot',        data.score_distribution?.hot_80_plus ?? '—');
  setText('stat-warm',       data.score_distribution?.warm_50_79  ?? '—');
  setText('stat-escalations',data.escalations_pending ?? '—');
  setText('stat-connected',  data.call_results?.connected ?? 0);
  setText('stat-no-answer',  data.call_results?.no_answer ?? 0);

  renderBarChart('lead-type-chart', toBarData(data.lead_types));
  renderBarChart('country-chart',   (data.top_countries || []).map(c => ({ label: c.country, value: c.count })));
  renderBarChart('membership-chart',toBarData(data.membership_potential), ['hot','warm','cold']);
}

function setText(id, value) {
  const el = document.querySelector(`#${id} .stat-value`);
  if (el) el.textContent = value ?? '—';
}

function toBarData(obj) {
  if (!obj) return [];
  return Object.entries(obj).map(([k, v]) => ({ label: k, value: v }));
}

// ── Hot Leads ─────────────────────────────────────────────────────────

async function loadHotLeads() {
  const leads = await apiFetch('/dashboard/hot-leads');
  const tbody = document.getElementById('hot-leads-body');
  if (!leads || !leads.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="loading">No hot leads yet</td></tr>';
    return;
  }
  tbody.innerHTML = leads.map(l => `
    <tr>
      <td><strong>${esc(l.company_name)}</strong></td>
      <td>${esc(l.country)}</td>
      <td>${esc(l.lead_type)}</td>
      <td><strong>${l.lead_score}</strong></td>
      <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"
          title="${esc(l.next_action)}">${esc(l.next_action)}</td>
    </tr>
  `).join('');
}

// ── Escalations ────────────────────────────────────────────────────────

async function loadEscalations() {
  const leads = await apiFetch('/dashboard/escalations');
  const tbody = document.getElementById('escalations-body');
  if (!leads || !leads.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="loading">No pending escalations</td></tr>';
    return;
  }
  tbody.innerHTML = leads.map(l => `
    <tr>
      <td><strong>${esc(l.company_name)}</strong></td>
      <td>${esc(l.country)}</td>
      <td><strong>${l.lead_score}</strong></td>
      <td style="max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"
          title="${esc(l.escalation_reason)}">${esc(l.escalation_reason)}</td>
      <td>${esc(l.phone)}</td>
    </tr>
  `).join('');
}

// ── Call Queue ─────────────────────────────────────────────────────────

async function loadQueue() {
  const limit = document.getElementById('queue-limit').value || 20;
  const leads = await apiFetch(`/leads/queue?limit=${limit}`);
  const tbody = document.getElementById('queue-body');
  if (!leads || !leads.length) {
    tbody.innerHTML = '<tr><td colspan="9" class="loading">Queue is empty</td></tr>';
    return;
  }
  tbody.innerHTML = leads.map(l => `
    <tr data-lead-id="${esc(l.lead_id)}">
      <td><input type="checkbox" class="row-check" value="${esc(l.lead_id)}" /></td>
      <td><strong>${esc(l.company_name)}</strong></td>
      <td>${esc(l.country)}</td>
      <td>${esc(l.phone)}</td>
      <td>${esc(l.lead_type)}</td>
      <td>${l.lead_score ?? '—'}</td>
      <td>${urgencyBadge(l.urgency)}</td>
      <td>${esc(l.call_status)}</td>
      <td>
        <button class="small" onclick="callLead('${esc(l.lead_id)}')">Call</button>
      </td>
    </tr>
  `).join('');
}

function urgencyBadge(u) {
  if (u === 'hot')  return '<span class="urgency-hot">hot</span>';
  if (u === 'warm') return '<span class="urgency-warm">warm</span>';
  return '<span class="urgency-cold">cold</span>';
}

function toggleAll(masterCb) {
  document.querySelectorAll('.row-check').forEach(cb => cb.checked = masterCb.checked);
}

async function callLead(leadId) {
  const ok = await apiFetch('/calls/initiate', 'POST', { lead_id: leadId });
  if (ok) toast(`Call initiated for ${leadId}`, 'success');
}

async function confirmBulkCall() {
  const checked = [...document.querySelectorAll('.row-check:checked')].map(cb => cb.value);
  if (!checked.length) { toast('Select at least one lead', 'error'); return; }
  if (!confirm(`Start calls for ${checked.length} leads?`)) return;
  const ok = await apiFetch('/calls/bulk-initiate', 'POST', { lead_ids: checked, max_concurrent: 3 });
  if (ok) toast(`Queued ${checked.length} calls`, 'success');
}

// ── Report ─────────────────────────────────────────────────────────────

async function generateReport() {
  const ok = await apiFetch('/reports/generate', 'POST');
  if (ok) toast('Report generation started', 'success');
}

// ── Bar Chart ──────────────────────────────────────────────────────────

function renderBarChart(containerId, items, colorClasses = []) {
  const el = document.getElementById(containerId);
  if (!el || !items.length) { if (el) el.innerHTML = '<p style="color:#999;padding:8px">No data</p>'; return; }

  const max = Math.max(...items.map(i => i.value), 1);
  el.innerHTML = items.slice(0, 8).map((item, idx) => {
    const pct = Math.round((item.value / max) * 100);
    const cls = colorClasses[idx] || '';
    return `
      <div class="chart-bar-row">
        <div class="chart-bar-label" title="${esc(item.label)}">${esc(item.label)}</div>
        <div class="chart-bar-track">
          <div class="chart-bar-fill ${cls}" style="width:${pct}%"></div>
        </div>
        <div class="chart-bar-value">${item.value}</div>
      </div>`;
  }).join('');
}

// ── Utilities ──────────────────────────────────────────────────────────

async function apiFetch(path, method = 'GET', body = null) {
  try {
    const opts = {
      method,
      headers: { 'Content-Type': 'application/json' },
    };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(API + path, opts);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      toast(err.detail || `Error ${res.status}`, 'error');
      return null;
    }
    return await res.json();
  } catch (e) {
    toast('Network error: ' + e.message, 'error');
    return null;
  }
}

function esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function toast(msg, type = '') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = 'toast' + (type ? ' ' + type : '');
  clearTimeout(el._t);
  el._t = setTimeout(() => { el.className = 'toast hidden'; }, 4000);
}
