// ===================== OFFSEC JOURNAL — CLIENT APP =====================
// Wires the static markup in index.html to the seed data in data.js.
// When the FastAPI backend lands this file swaps DATA.* reads for fetch()
// calls against /api/* endpoints and keeps the DOM wiring.

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const state = {
  currentPage: 'overview',
  drawerPerson: null,
  scheduleInteraction: 'hover',
  sidebarStyle: 'full',
  overviewWeeks: 5,
  online: false,   // set true once /api/health responds
};

// ===================== NAVIGATION =====================
function goToPage(id) {
  $$('.nav-item').forEach(n => n.classList.toggle('active', n.dataset.page === id));
  $$('.page').forEach(p => p.classList.remove('active'));
  const pg = document.getElementById('page-' + id);
  if (pg) pg.classList.add('active');
  state.currentPage = id;
  document.getElementById('main').scrollTop = 0;
  // Re-run searches / refresh journal list when entering those pages
  if (id === 'search' && state.online) runSearch();
  if (id === 'journal') renderJournal(_activeJournalFilter());
  if (id === 'project-detail') {
    const fallback = (DATA.projects && DATA.projects[0] && DATA.projects[0].code) || null;
    const code = state._editingProject || fallback;
    if (code) renderProjectDetail(code);
  }
  if (id === 'map') initMap();
}

function renderProjectDetail(code) {
  state._editingProject = code;
  const H = _escapeHtml;
  const pr = (DATA.projects || []).find(p => p.code === code);

  // Header (title, breadcrumb, sub)
  const titleEl = $('#project-detail-title');
  if (titleEl) titleEl.innerHTML = `<span class="mono">${H(code)}</span>`;
  const crumb = $('#project-detail-breadcrumb');
  if (crumb) crumb.textContent = `/projects/${code}`;
  const subEl = $('#project-detail-sub');
  if (subEl) {
    subEl.textContent = pr
      ? `${pr.type || '—'} · ${pr.client || pr.client_alias || '—'} · ${pr.window || '—'} · ${pr.status || '—'}`
      : 'proyecto no encontrado en cache';
  }

  // Required skills × team
  const tbody = $('#project-detail-reqskills-body');
  if (tbody) {
    const reqs = (pr && pr.required_skills) || [];
    if (reqs.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" class="text-muted small">Sin skills requeridas</td></tr>';
    } else {
      tbody.innerHTML = reqs.map(rs => {
        const matches = (DATA.people || [])
          .filter(p => !p.archived)
          .map(p => {
            const s = (p.skills || []).find(x => x.id === rs.skill_id);
            return s && s.lvl > 0 ? { id: p.id, lvl: s.lvl } : null;
          })
          .filter(Boolean)
          .sort((a, b) => b.lvl - a.lvl);
        const best = matches[0];
        const matchStr = matches.length === 0
          ? '— sin nadie con esta skill —'
          : matches.slice(0, 3).map(m => `${m.id} L${m.lvl}`).join(', ');
        let gap;
        if (!best) gap = `<span class="wf-badge rose">sin cobertura</span>`;
        else if (best.lvl >= rs.min_level) gap = `<span class="wf-badge green">✓</span>`;
        else gap = `<span class="wf-badge rose">-${rs.min_level - best.lvl} nivel${rs.min_level - best.lvl === 1 ? '' : 'es'}</span>`;
        return `<tr><td class="mono">${H(rs.skill_id)}</td><td>${rs.weight}</td><td>L${rs.min_level}</td><td class="small">${H(matchStr)}</td><td>${gap}</td></tr>`;
      }).join('');
    }
  }

  // Coverage bar + badge
  const fill = $('#project-detail-coverage-fill');
  const badge = $('#project-detail-coverage-badge');
  if (fill && badge) {
    const cov = pr && pr.coverage != null ? pr.coverage : null;
    if (cov == null) {
      fill.style.width = '0%';
      badge.textContent = '—';
      badge.className = 'wf-badge gray';
    } else {
      fill.style.width = `${cov}%`;
      const cls = cov >= 80 ? 'green' : cov >= 40 ? 'amber' : 'rose';
      const colorVar = cov >= 80 ? 'rgba(95,206,111,0.5)' : cov >= 40 ? 'rgba(240,184,48,0.5)' : 'rgba(240,96,112,0.5)';
      fill.style.background = colorVar;
      badge.textContent = `${cov}%`;
      badge.className = `wf-badge ${cls}`;
    }
  }

  // Assignments actuales
  const assignEl = $('#project-detail-assignments');
  if (assignEl) {
    const active = ((pr && pr._raw_assignments) || []).filter(a => !a.archived);
    if (active.length === 0) {
      assignEl.innerHTML = `<div class="wf-placeholder" style="min-height:80px;">Sin assignments${pr && pr.status === 'pipeline' ? '<br>(proyecto en pipeline)' : ''}</div>`;
    } else {
      assignEl.innerHTML = active.map(a => `
        <div class="assign-row" style="padding:8px 0;border-bottom:1px dashed var(--border);display:flex;justify-content:space-between;align-items:center;gap:8px;">
          <div style="flex:1;min-width:0;">
            <div class="fw-600 mono">${H(a.person_id)} <span class="wf-badge gray">${a.dedication_pct}%</span></div>
            <div class="small text-muted">${H(a.role || 'executor')} · ${H(a.start || '')} → ${H(a.end || '')}</div>
          </div>
          <button class="btn small danger assign-unassign-btn" data-person-id="${H(a.person_id)}" data-project-code="${H(code)}" title="Desasignar">✕</button>
        </div>
      `).join('');
      assignEl.querySelectorAll('.assign-unassign-btn').forEach(btn => {
        btn.addEventListener('click', () => openUnassignConfirm(btn.dataset.personId, btn.dataset.projectCode));
      });
    }
  }

  // Timeline (window_start → window_end con marcas semanales)
  const tl = $('#project-detail-timeline');
  if (tl) {
    if (pr && pr.window_start && pr.window_end) {
      const s = new Date(pr.window_start);
      const e = new Date(pr.window_end);
      const weeks = Math.max(1, Math.ceil((e - s) / (7 * 86400000)));
      const fmt = d => `${String(d.getUTCMonth() + 1).padStart(2, '0')}-${String(d.getUTCDate()).padStart(2, '0')}`;
      tl.innerHTML = `
        <div class="timeline-weeks"><span>${H(pr.window_start)}</span><span class="text-muted">${weeks} sem.</span><span>${H(pr.window_end)}</span></div>
        <div class="timeline-axis"></div>
        <div class="timeline-bar">${H(pr.type || 'proyecto')} — ${weeks} semana${weeks === 1 ? '' : 's'} (${fmt(s)} → ${fmt(e)})</div>
      `;
    } else {
      tl.innerHTML = `
        <div class="timeline-weeks"><span class="text-muted small">—</span></div>
        <div class="timeline-axis"></div>
        <div class="timeline-bar text-muted small">Sin ventana definida</div>
      `;
    }
  }

  // Notes
  const path = $('#project-detail-notes-path');
  if (path) path.textContent = `notes/projects/${code}.md`;
  const btn = $('#project-notes-submit');
  if (btn) {
    btn.onclick = () => submitNote('project', code,
      'project-notes-textarea', 'project-notes-tags',
      'project-detail-notes', null);
  }
  refreshNotes('project', code, 'project-detail-notes', null);
}

$$('.nav-item').forEach(item => {
  item.addEventListener('click', () => goToPage(item.dataset.page));
});

// ===================== DRAWER =====================
function openDrawer(personId) {
  const p = DATA.people.find(x => x.id === personId);
  if (!p) return;
  state.drawerPerson = p;

  $('#drawer-name').textContent = p.name;
  $('#drawer-id').textContent = p.id;
  $('#drawer-meta').textContent = `${p.office} · ${p.level} · FTE ${p.fte.toFixed(1)} · desde ${p.start}`;
  $('#drawer-fullpage').onclick = (e) => { e.preventDefault(); closeDrawer(); renderPersonDetail(p); goToPage('person-detail'); };

  $('#drawer-radar').innerHTML = buildRadarSvg(levelsForRadar(p), 260);
  $('#drawer-skills').innerHTML = p.skills
    .filter(s => s.lvl > 0)
    .slice(0, 8)
    .map(s => `<span class="wf-badge green">${s.id} L${s.lvl}</span>`).join('');

  $('#drawer-assignments').innerHTML = p.assignments.length
    ? p.assignments.map(a => `
        <div style="display:flex;justify-content:space-between;">
          <span class="mono">${a.project}</span>
          <span>${a.pct}% · ${a.role}</span>
        </div>`).join('')
    : '<div class="text-muted small">Sin assignments</div>';

  $('#drawer-notes').innerHTML = p.notes.length
    ? `<div class="note-item"><div class="note-meta">${p.notes[0].date} — ${p.notes[0].author}</div><div class="note-body">${p.notes[0].body}</div></div>`
    : '<em>Sin notas</em>';

  document.getElementById('drawer-overlay').classList.add('open');
}

function closeDrawer() {
  document.getElementById('drawer-overlay').classList.remove('open');
}

// ===================== MODALS =====================
function openModal(id) { document.getElementById(id).classList.add('open'); }
function closeModal(id) { document.getElementById(id).classList.remove('open'); }
$$('.modal-overlay').forEach(m => m.addEventListener('click', e => {
  if (e.target === m) m.classList.remove('open');
}));

async function confirmReject() {
  const id = state._rejectingId;
  const reason = (document.querySelector('#reject-modal textarea')?.value || '').trim();
  if (!reason) { _toast('La razón es obligatoria', 'warn'); return; }
  if (state.online && id) {
    try {
      await api.rejectJournal(id, reason);
    } catch (err) {
      _toast(`reject falló: ${err.message}\n${err.body || ''}`, 'error');
      return;
    }
  }
  closeModal('reject-modal');
  state._rejectingId = null;
  const ta = document.querySelector('#reject-modal textarea');
  if (ta) ta.value = '';
  if (state.online) await refreshAll();
  else if (state.currentPage === 'journal') await renderJournal(_activeJournalFilter());
}

function openRejectDialog(subject, entryId) {
  $('#reject-subject').textContent = subject || 'skill_update · 01HYXZ...';
  state._rejectingId = entryId || null;
  openModal('reject-modal');
}

// ===================== RADAR SVG =====================
// Picks the top-10 skills by level (alpha as tiebreak), then sorts those 10
// alphabetically for stable axis positions as the person's skills evolve.
const RADAR_MAX_AXES = 10;

function levelsForRadar(person) {
  const ranked = (person.skills || [])
    .filter(s => s && s.id && (Number(s.lvl) || 0) > 0)
    .slice()
    .sort((a, b) => (Number(b.lvl) || 0) - (Number(a.lvl) || 0) || String(a.id || '').localeCompare(String(b.id || '')))
    .slice(0, RADAR_MAX_AXES)
    .sort((a, b) => String(a.id || '').localeCompare(String(b.id || '')));
  return {
    axes: ranked.map(s => s.id),
    levels: ranked.map(s => Math.max(0, Math.min(5, Number(s.lvl) || 0))),
  };
}

function _radarLabelLines(label) {
  if (label.length <= 14) return [label];
  const parts = label.split(/[_\-\s]/);
  if (parts.length === 1) return [label.slice(0, 13) + '…'];
  // Greedy: split into 2 lines roughly balanced by total chars
  const total = label.length;
  let acc = 0, mid = 0;
  for (let i = 0; i < parts.length - 1; i++) {
    acc += parts[i].length + 1;
    if (acc >= total / 2) { mid = i + 1; break; }
  }
  if (mid === 0) mid = Math.max(1, Math.ceil(parts.length / 2));
  return [parts.slice(0, mid).join('_'), parts.slice(mid).join('_')];
}

function buildRadarSvg(data, size = 220) {
  const { axes, levels } = data;
  const N = axes.length;
  const VB = 320;
  const cx = VB / 2, cy = VB / 2, maxR = 90, labelR = maxR + 14;

  if (N < 3) {
    const msg = N === 0 ? 'Sin skills registradas' : `Solo ${N} skill${N === 1 ? '' : 's'} (mín 3 para radar)`;
    return `<svg viewBox="0 0 ${VB} ${VB}" style="max-width:${size}px;width:100%;height:auto;display:block;"><text x="${cx}" y="${cy}" text-anchor="middle" fill="var(--text2)" font-size="12" font-family="JetBrains Mono, monospace">${_escapeHtml(msg)}</text></svg>`;
  }

  const angleAt = i => -Math.PI / 2 + (i * 2 * Math.PI) / N;

  let guides = '';
  for (let L = 1; L <= 5; L++) {
    const pts = [];
    for (let i = 0; i < N; i++) {
      const a = angleAt(i), r = (L / 5) * maxR;
      pts.push(`${(cx + r * Math.cos(a)).toFixed(2)},${(cy + r * Math.sin(a)).toFixed(2)}`);
    }
    guides += `<polygon points="${pts.join(' ')}"/>`;
  }

  let spokes = '';
  for (let i = 0; i < N; i++) {
    const a = angleAt(i);
    spokes += `<line x1="${cx}" y1="${cy}" x2="${(cx + maxR * Math.cos(a)).toFixed(2)}" y2="${(cy + maxR * Math.sin(a)).toFixed(2)}"/>`;
  }

  const dataPts = levels.map((lvl, i) => {
    const a = angleAt(i), r = (lvl / 5) * maxR;
    return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
  });
  const polyPts = dataPts.map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`).join(' ');
  const dots = dataPts.map(([x, y]) => `<circle cx="${x.toFixed(2)}" cy="${y.toFixed(2)}" r="3"/>`).join('');

  const maxLen = axes.reduce((m, lbl) => Math.max(m, lbl.length), 0);
  const fontSize = maxLen <= 10 ? 11 : maxLen <= 16 ? 9.5 : 8.5;

  const labels = axes.map((lbl, i) => {
    const a = angleAt(i);
    const cosA = Math.cos(a), sinA = Math.sin(a);
    const x = cx + labelR * cosA;
    const y = cy + labelR * sinA;
    const anchor = cosA > 0.3 ? 'start' : cosA < -0.3 ? 'end' : 'middle';
    // Push the first line above when label is on top half so it doesn't ride the polygon
    const lines = _radarLabelLines(lbl);
    const baseDy = sinA < -0.6 ? -2 : sinA > 0.6 ? 10 : 4;
    const yStart = y + baseDy - (lines.length > 1 && sinA < 0 ? (lines.length - 1) * (fontSize + 1) : 0);
    const tspans = lines.map((line, li) => `<tspan x="${x.toFixed(1)}" dy="${li === 0 ? 0 : fontSize + 1}">${_escapeHtml(line)}</tspan>`).join('');
    const lvl = levels[i];
    return `<text x="${x.toFixed(1)}" y="${yStart.toFixed(1)}" text-anchor="${anchor}"><title>${_escapeHtml(lbl)} · L${lvl}</title>${tspans}</text>`;
  }).join('');

  return `
    <svg viewBox="0 0 ${VB} ${VB}" style="max-width:${size}px;width:100%;height:auto;display:block;">
      <g fill="none" stroke="var(--border-strong)" stroke-dasharray="3 3" stroke-width="1">${guides}</g>
      <g stroke="var(--border-strong)" stroke-width="1" stroke-dasharray="2 3">${spokes}</g>
      <polygon points="${polyPts}" fill="rgba(30,155,224,0.25)" stroke="var(--accent)" stroke-width="1.5"/>
      <g fill="var(--accent-strong)">${dots}</g>
      <g fill="var(--text2)" font-family="JetBrains Mono, monospace" font-size="${fontSize}">${labels}</g>
    </svg>
  `;
}

// ===================== HEATMAP HELPERS =====================
// 7-tier scale: empty → 5 progressive blues → amber (near-full) → red (over).
// The jump from blue to amber at 80% flags "near capacity" visually, and the
// red band is reserved exclusively for over-allocation (>100%).
function hmColor(v) {
  if (v > 100) return 'rgba(240, 96, 112, 0.78)';   // over-allocated
  if (v >= 81) return 'rgba(240, 184, 48, 0.62)';   // near capacity (amber)
  if (v >= 61) return 'rgba(30, 155, 224, 0.80)';   // high load
  if (v >= 41) return 'rgba(30, 155, 224, 0.58)';   // medium-high
  if (v >= 21) return 'rgba(30, 155, 224, 0.38)';   // medium
  if (v >= 1)  return 'rgba(30, 155, 224, 0.20)';   // low
  return 'rgba(30, 155, 224, 0.04)';                // empty
}

// ===================== OVERVIEW =====================
function buildOverviewHeatmap(weeks) {
  state.overviewWeeks = weeks;
  const people = (DATA.people || []).filter(p => !p.archived).map(p => p.id);
  const el = $('#overview-heatmap');
  if (!people.length) {
    el.innerHTML = '<div class="wf-placeholder" style="min-height:60px;">Sin personas activas</div>';
    return;
  }
  const baseWeek = 15;
  const cols = [];
  for (let i = 0; i < weeks; i++) {
    const w = baseWeek + i;
    cols.push(w <= 52 ? 'W' + w : 'W' + (w - 52));
  }
  const grid = document.createElement('div');
  grid.className = 'hm-grid';

  // Dynamic sizing based on column count so cells stay inside the card.
  const n = cols.length;
  const labelColW   = n > 17 ? 48 : n > 8 ? 60 : 84;
  const hdrFontSize = n > 21 ? 8  : n > 12 ? 9  : n > 8 ? 10 : 11;
  const cellFontSize = n > 21 ? 8 : n > 17 ? 8.5 : n > 12 ? 9 : n > 8 ? 10 : 11;
  const pctSuffix    = n > 17 ? '' : '%';
  const stripW       = n > 17;
  grid.style.gridTemplateColumns = `${labelColW}px repeat(${n}, minmax(0, 1fr))`;
  grid.style.gap = n > 17 ? '1px' : '2px';

  let html = '<div class="hm-header"></div>';
  cols.forEach(c => {
    const label = stripW ? c.replace('W', '') : c;
    html += `<div class="hm-header" style="font-size:${hdrFontSize}px;padding:2px 1px;">${label}</div>`;
  });
  people.forEach(p => {
    html += `<div class="hm-header" style="justify-content:flex-end;padding-right:6px;font-family:var(--font-mono);font-size:${Math.max(hdrFontSize, 10)}px;">${p}</div>`;
    cols.forEach((c, j) => {
      // Prefer live overview data when available on state._overviewMatrix (set after refreshAll).
      const source = (state._overviewMatrix && state._overviewMatrix[p])
        ? state._overviewMatrix[p]
        : (DATA.overviewPatterns[p] || []);
      const v = source[j % (source.length || 26)] || 0;
      const label = v ? `${v}${pctSuffix}` : '';
      html += `<div class="hm-cell" style="background:${hmColor(v)};font-size:${cellFontSize}px;" title="${p} ${c}: ${v}%">${label}</div>`;
    });
  });
  grid.innerHTML = html;
  el.innerHTML = '';
  el.appendChild(grid);

  // Normalize cell height across ALL ranges to the 2M-equivalent (8 cols at
  // aspect-ratio 3.2) so 1S, 2S, 3S, 1M, 2M, 3M, 4M, 5M, 6M all share the
  // same row height regardless of column count.
  requestAnimationFrame(() => {
    const refColW = (grid.clientWidth - labelColW) / 8;
    const refH = Math.max(20, refColW / 3.2);
    grid.querySelectorAll('.hm-cell').forEach(c => {
      c.style.height = refH + 'px';
      c.style.aspectRatio = 'auto';
    });
  });
}

function buildOverviewRangeButtons() {
  const el = $('#overview-range-btns');
  const ranges = [
    { label: '1S', w: 1 }, { label: '2S', w: 2 }, { label: '3S', w: 3 },
    { label: '1M', w: 4 }, { label: '2M', w: 8 }, { label: '3M', w: 12 },
    { label: '4M', w: 17 }, { label: '5M', w: 21 }, { label: '6M', w: 26 },
  ];
  el.innerHTML = ranges.map(r => `<button class="hm-range-btn${r.w === 4 ? ' active' : ''}" data-w="${r.w}">${r.label}</button>`).join('');
  $$('#overview-range-btns .hm-range-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      $$('#overview-range-btns .hm-range-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      buildOverviewHeatmap(Number(btn.dataset.w));
    });
  });
}

function renderOverviewGaps() {
  const H = _escapeHtml;
  $('#overview-gaps').innerHTML = DATA.skillGaps.slice(0, 3).map(g => `
    <div style="display:flex;justify-content:space-between;align-items:center;">
      <span class="mono" style="font-size:13px;">${H(g.skill)}</span>
      <span class="wf-badge ${g.severity}">${g.have === 0 ? 'sin cobertura' : 'déficit ' + g.deficit}</span>
    </div>
  `).join('');
}

function renderOverviewWarnings() {
  const H = _escapeHtml;
  const countEl = document.getElementById('overview-warnings-count');
  if (countEl) countEl.textContent = `(${DATA.coherenceWarnings.length})`;
  $('#overview-warnings').innerHTML = DATA.coherenceWarnings.map(w => `
    <div class="warn-box">
      <span class="wf-badge amber" style="flex-shrink:0;">warning</span>
      <div style="flex:1;">
        <div class="fw-600" style="margin-bottom:2px;">
          <a href="#" data-person="${H(w.person)}" class="mono text-accent warning-person-link">${H(w.person)}</a> — ${H(w.rule)}
        </div>
        <div class="small text-muted">${H(w.detail)}</div>
      </div>
    </div>
  `).join('');
  // Delegated click handler — avoids inline onclick with interpolated JS
  $$('#overview-warnings .warning-person-link').forEach(a => a.addEventListener('click', (e) => {
    e.preventDefault();
    renderPersonById(a.dataset.person);
    goToPage('person-detail');
  }));
}

function renderOverviewJournal() {
  const H = _escapeHtml;
  $('#overview-journal').innerHTML = DATA.recentJournal.map(j => `
    <div style="display:flex;gap:12px;align-items:center;font-size:14px;">
      <span class="wf-badge ${j.status === 'applied' ? 'green' : j.status === 'pending' ? 'amber' : 'gray'}">${H(j.status)}</span>
      <span class="mono text-muted" style="font-size:11px;">${H(j.kind)}</span>
      <span>${H(j.text)}</span>
      <span class="mono text-muted" style="font-size:11px;margin-left:auto;">${H(j.ago)}</span>
    </div>
  `).join('');
}

// ===================== PEOPLE =====================
function _peopleFilterState() {
  return {
    office: ($('#people-filter-office')?.value || '').trim().toLowerCase(),
    level: ($('#people-filter-level')?.value || '').trim().toLowerCase(),
    skill: ($('#people-filter-skill')?.value || '').trim().toLowerCase(),
  };
}

function _populatePeopleOfficeFilter() {
  const sel = $('#people-filter-office');
  if (!sel) return;
  const offices = Array.from(new Set((DATA.people || []).map(p => p.office).filter(Boolean))).sort();
  const current = sel.value;
  sel.innerHTML = '<option value="">Todas las oficinas</option>' +
    offices.map(o => `<option value="${_escapeHtml(o)}">${_escapeHtml(o)}</option>`).join('');
  if (offices.includes(current)) sel.value = current;
}

function renderPeopleTable() {
  const H = _escapeHtml;
  const tbody = $('#people-tbody');
  if (!tbody) return;
  _populatePeopleOfficeFilter();
  const f = _peopleFilterState();
  const rows = (DATA.people || []).filter(p => !p.archived).filter(p => {
    if (f.office && (p.office || '').toLowerCase() !== f.office) return false;
    if (f.level && (p.level || '').toLowerCase() !== f.level) return false;
    if (f.skill) {
      const has = (p.skills || []).some(s => s.id.toLowerCase().includes(f.skill) && s.lvl > 0);
      if (!has) return false;
    }
    return true;
  });
  if (rows.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-muted small" style="text-align:center;padding:14px;">Sin resultados con esos filtros</td></tr>';
    return;
  }
  tbody.innerHTML = rows.map(p => `
    <tr data-person-id="${H(p.id)}" class="people-row">
      <td class="mono">${H(p.id)}</td>
      <td>${H(p.name)}</td>
      <td>${H(p.office)}</td>
      <td><span class="wf-badge ${p.warning ? 'amber' : (p.level === 'senior' || p.level === 'master') ? 'green' : 'gray'}">${H(p.level)}${p.warning ? ' ⚠' : ''}</span></td>
      <td>${Number(p.load)}%</td>
      <td>${p.warning ? `<span class="text-warn" title="${H(p.warning)}">⚠</span>` : ''}</td>
    </tr>
  `).join('');
  $$('#people-tbody .people-row').forEach(tr =>
    tr.addEventListener('click', () => openDrawer(tr.dataset.personId))
  );
}

function wirePeopleFilters() {
  ['#people-filter-office', '#people-filter-level'].forEach(sel => {
    const el = $(sel);
    if (el) el.addEventListener('change', () => renderPeopleTable());
  });
  const skill = $('#people-filter-skill');
  if (skill) {
    let t;
    skill.addEventListener('input', () => {
      clearTimeout(t);
      t = setTimeout(() => renderPeopleTable(), 200);
    });
  }
}

// ===================== PERSON DETAIL =====================
function renderPersonById(id) {
  const p = DATA.people.find(x => x.id === id);
  if (p) renderPersonDetail(p);
}

function renderPersonDetail(p) {
  const H = _escapeHtml;
  state._currentPerson = p.id;
  $('#person-detail-path').textContent = `/people/${p.id}`;
  $('#person-detail-name').textContent = p.name;
  const levelBadge = `<span class="wf-badge ${p.warning ? 'amber' : 'green'}">${H(p.level)}${p.warning ? ' ⚠' : ''}</span>`;
  $('#person-detail-meta').innerHTML = `
    <span class="mono text-accent">${H(p.id)}</span> · ${H(p.office)} · ${H(p.tz)} · ${levelBadge}
    FTE ${Number(p.fte).toFixed(1)} · desde ${H(p.start)} · idiomas: ${H((p.langs || []).join(', '))}
  `;

  $('#person-detail-radar').innerHTML = buildRadarSvg(levelsForRadar(p), 480);

  $('#person-detail-skills').innerHTML = p.skills.map(s => `
    <tr style="cursor:pointer;" onclick='openEditSkill("${p.id}", ${JSON.stringify(s).replace(/"/g,"&quot;")})' title="Click para editar nivel">
      <td class="mono">${s.id}</td>
      <td><span class="wf-badge ${s.lvl >= 3 ? 'green' : 'gray'}">L${s.lvl}</span></td>
      <td class="mono" style="font-size:12px;">${s.last || '—'}</td>
      <td class="${s.growth ? 'text-accent' : 'text-muted'}">${s.growth ? '★ interesado' : '—'}</td>
    </tr>
  `).join('') + `
    <tr><td colspan="4" style="text-align:center;">
      <button class="btn small" onclick="openEditSkill('${p.id}', null)">+ Añadir skill</button>
      <button class="btn small danger" style="margin-left:8px;" onclick="openArchiveConfirm('person','${p.id}')">Archivar persona</button>
    </td></tr>`;

  $('#person-detail-assignments').innerHTML = p.assignments.length
    ? p.assignments.map(a => `
        <tr>
          <td class="mono">${H(a.project)}</td>
          <td>${H(a.role)}</td>
          <td>${Number(a.pct) || 0}%</td>
          <td>${H(a.window)}</td>
          <td><button class="btn small danger person-unassign-btn" data-person-id="${H(p.id)}" data-project-code="${H(a.project)}" title="Desasignar">✕</button></td>
        </tr>
      `).join('')
    : '<tr><td colspan="5" class="text-muted small">Sin assignments activos</td></tr>';
  $$('#person-detail-assignments .person-unassign-btn').forEach(btn => {
    btn.addEventListener('click', () => openUnassignConfirm(btn.dataset.personId, btn.dataset.projectCode));
  });

  const coh = p.coherence;
  $('#person-detail-coherence').innerHTML = coh.ok
    ? `<div style="font-size:14px;color:var(--accent-strong);">${coh.msg}</div>
       <div class="warn-box mt-md" style="opacity:0.55;">
         <span class="wf-badge amber" style="flex-shrink:0;">—</span>
         <div>
           <div class="small text-muted" style="font-style:italic;">Ejemplo si hubiera warning:</div>
           <div class="mono" style="font-size:11px;color:var(--warn);margin-top:4px;">insufficient_skill_coverage</div>
           <div class="small" style="margin-top:2px;">Regla senior pide ≥5 PersonSkill level≥1; actuales: 4.</div>
         </div>
       </div>`
    : `<div class="warn-box">
         <span class="wf-badge amber" style="flex-shrink:0;">warning</span>
         <div>
           <div class="mono fw-600" style="font-size:12px;color:var(--warn);">${coh.msg}</div>
           <div class="small mt-sm">${coh.detail}</div>
         </div>
       </div>`;

  const avail = p.availability.length
    ? p.availability.map(a => `
        <tr>
          <td><span class="wf-badge ${a.kind === 'pto' ? 'amber' : 'gray'}">${a.kind}</span></td>
          <td class="mono" style="font-size:12px;">${a.window}</td>
          <td>${a.pct}%</td>
          <td>${a.reason}</td>
          <td><span class="wf-badge green">${a.status}</span></td>
        </tr>
      `).join('')
    : '<tr><td colspan="5" class="text-muted small">Sin entradas de disponibilidad</td></tr>';
  $('#person-detail-avail').innerHTML = avail;

  // Seed render first — gives an instant fallback when offline
  $('#person-detail-notes').innerHTML = p.notes.length
    ? p.notes.map(n => `
        <div class="note-item">
          <div class="note-meta">${_escapeHtml(n.date)} | ${_escapeHtml(n.author)} | tags: ${_escapeHtml((n.tags || []).join(', '))}</div>
          <div class="note-body">${_escapeHtml(n.body)}</div>
        </div>
      `).join('')
    : '<div class="text-muted small">Sin notas</div>';
  $('#person-detail-notes-page').textContent = `${p.notes.length} nota(s)`;

  // Live override: replace with real notes from the markdown file
  if (state.online) refreshNotes('person', p.id, 'person-detail-notes', 'person-detail-notes-page');

  // Rewire the submit button for the current person id
  const btn = $('#person-notes-submit');
  if (btn) {
    btn.onclick = () => submitNote('person', p.id,
      'person-notes-textarea', 'person-notes-tags',
      'person-detail-notes', 'person-detail-notes-page');
  }
}

// ===================== PROJECTS =====================
function renderProjects() {
  // Kanban columns
  const cols = {
    pipeline: DATA.projects.filter(p => p.status === 'pipeline'),
    active:   DATA.projects.filter(p => p.status === 'active'),
    closed:   DATA.projects.filter(p => p.status === 'closed'),
  };
  const colDef = [
    { key: 'pipeline', badge: 'amber', label: 'pipeline' },
    { key: 'active',   badge: 'green', label: 'active' },
    { key: 'closed',   badge: 'gray',  label: 'closed' },
  ];
  const H = _escapeHtml;
  $('#projects-kanban-view').innerHTML = colDef.map(c => {
    const items = cols[c.key];
    const cards = items.length
      ? items.map(p => `
          <div class="kanban-card project-card" data-code="${H(p.code)}">
            <div class="kanban-card-title mono">${H(p.code)}</div>
            <div class="kanban-card-meta">${H(p.type)} · ${H(p.client)}</div>
            <div class="kanban-card-meta">${H(p.window)}</div>
            <div class="mt-sm">
              <span class="wf-badge ${coverBadge(p.coverage)}">${p.coverage == null ? 'cobertura —' : 'cobertura ' + Number(p.coverage) + '%'}</span>
            </div>
          </div>`).join('')
      : `<div class="wf-placeholder" style="min-height:100px;">Sin proyectos ${c.label === 'closed' ? 'cerrados' : H(c.label)} este filtro</div>`;
    return `
      <div class="kanban-col">
        <div class="kanban-col-title">
          <span class="wf-badge ${c.badge}">${c.label}</span>
          <span class="kanban-col-count">${items.length}</span>
        </div>
        ${cards}
      </div>`;
  }).join('');

  // Table view
  $('#projects-tbody').innerHTML = DATA.projects.map(p => `
    <tr class="project-row" data-code="${H(p.code)}">
      <td class="mono">${H(p.code)}</td>
      <td>${H(p.type)}</td>
      <td>${H(p.client)}</td>
      <td>${H(p.window)}</td>
      <td><span class="wf-badge ${p.status === 'active' ? 'green' : p.status === 'pipeline' ? 'amber' : 'gray'}">${H(p.status)}</span></td>
      <td><span class="wf-badge ${coverBadge(p.coverage)}">${p.coverage == null ? '—' : Number(p.coverage) + '%'}</span></td>
      <td>${Number(p.assigned)}/${Number(p.total)}</td>
    </tr>
  `).join('');

  // Delegated handlers — no inline onclick
  $$('.project-card, .project-row').forEach(el => el.addEventListener('click', () => goToPage('project-detail')));
}

function coverBadge(cov) {
  if (cov == null) return 'gray';
  if (cov < 50) return 'rose';
  if (cov < 85) return 'amber';
  return 'green';
}

function wireProjectTabs() {
  $$('#projects-tabs .tab').forEach(t => {
    t.addEventListener('click', () => {
      $$('#projects-tabs .tab').forEach(x => x.classList.remove('active'));
      t.classList.add('active');
      const v = t.dataset.view;
      $('#projects-kanban-view').style.display = v === 'kanban' ? '' : 'none';
      $('#projects-table-view').style.display = v === 'table' ? '' : 'none';
    });
  });
}

// ===================== CLIENTS =====================
function renderClients() {
  const H = _escapeHtml;
  $('#clients-list').innerHTML = DATA.clients.map((c, i) => {
    const projects = c.projects || [];
    const activeCount = projects.filter(p => p.status === 'active').length;
    return `
    <div class="client-list-item${i === 0 ? ' active' : ''}" data-client="${H(c.id)}">
      <div class="client-list-item-name">${H(c.name)}</div>
      <div class="client-list-item-meta">${projects.length} proyecto${projects.length === 1 ? '' : 's'} · ${activeCount} activo${activeCount === 1 ? '' : 's'}</div>
    </div>
  `;
  }).join('');
  $$('#clients-list .client-list-item').forEach(el => {
    el.addEventListener('click', () => {
      $$('#clients-list .client-list-item').forEach(x => x.classList.remove('active'));
      el.classList.add('active');
      renderClientDetail(el.dataset.client);
    });
  });
  if (DATA.clients.length > 0) renderClientDetail(DATA.clients[0].id);
}

function renderClientDetail(id) {
  const c = DATA.clients.find(x => x.id === id);
  if (!c) return;
  const H = _escapeHtml;
  const projects = c.projects || [];
  const contactsArr = c.contacts || [];
  const notesArr = c.notes || [];
  const projRows = projects.map(p => `
    <tr class="client-project-row" data-project-code="${H(p.code)}" style="cursor:pointer;">
      <td class="mono">${H(p.code)}</td>
      <td>${H(p.type)}</td>
      <td>${H(p.window)}</td>
      <td><span class="wf-badge ${p.status === 'active' ? 'green' : p.status === 'pipeline' ? 'amber' : 'gray'}">${H(p.status)}</span></td>
      <td><span class="wf-badge ${coverBadge(p.coverage)}">${H(p.coverage)}%</span></td>
    </tr>
  `).join('');
  const contacts = contactsArr.length
    ? contactsArr.map((k, idx) => `
        <div class="contact-row" data-client-id="${H(c.id)}" data-contact-idx="${idx}" style="display:flex;gap:12px;align-items:center;cursor:pointer;" title="Click para editar">
          <div class="avatar">${H(k.initials || (k.name || '?').split(' ').map(x=>x[0]).join('').slice(0,2).toUpperCase())}</div>
          <div>
            <div class="fw-600">${H(k.name)}</div>
            <div class="small text-muted">${H(k.role || '—')} · ${H(k.email || '')}</div>
          </div>
        </div>`).join('')
    : '<div class="wf-placeholder" style="min-height:60px;">Sin contactos aún</div>';
  const notes = notesArr.length
    ? notesArr.map(n => `<div class="note-item"><div class="note-meta">${H(n.date)} | ${H(n.author)}</div><div class="note-body">${H(n.body)}</div></div>`).join('')
    : '<div class="text-muted small">Sin notas</div>';

  state._currentClient = id;
  $('#client-detail').innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;">
      <div>
        <h2 class="page-title" style="font-size:24px;">${H(c.name)}</h2>
        <div class="small text-muted">Sector: ${H(c.sector)} · Tamaño: ${H(c.size)} · País: ${H(c.country)}</div>
      </div>
      <div style="display:flex;gap:8px;">
        <button class="btn small" id="client-detail-edit-btn">Editar</button>
        <span class="wf-badge green">${H(c.status)}</span>
      </div>
    </div>
    <div class="wf-card">
      <div class="wf-card-title">Descripción</div>
      <div style="font-size:14px;">${H(c.description)}</div>
    </div>
    <div class="wf-card">
      <div class="wf-card-title">Proyectos</div>
      <table class="wf-table">
        <thead><tr><th>Código</th><th>Tipo</th><th>Ventana</th><th>Status</th><th>Cobertura</th></tr></thead>
        <tbody>${projRows}</tbody>
      </table>
    </div>
    <div class="wf-card">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
        <div class="wf-card-title" style="margin:0;">Contactos</div>
        <div style="display:flex;gap:6px;">
          <button class="btn small" id="client-detail-contact-add-btn">+ Contacto</button>
          <button class="btn small danger" id="client-detail-archive-btn">Archivar</button>
        </div>
      </div>
      <div style="display:flex;flex-direction:column;gap:10px;">${contacts}</div>
    </div>
    <div class="wf-card">
      <div class="wf-card-title">Placeholders futuros</div>
      <div style="display:flex;gap:10px;flex-wrap:wrap;">
        <div class="wf-placeholder" style="flex:1;min-width:160px;min-height:70px;">SLA / Contrato</div>
        <div class="wf-placeholder" style="flex:1;min-width:160px;min-height:70px;">Facturación histórica</div>
        <div class="wf-placeholder" style="flex:1;min-width:160px;min-height:70px;">NPS / Satisfacción</div>
      </div>
    </div>
    <div class="wf-card">
      <div class="wf-card-title">Notas — <span class="mono small">notes/clients/${H(c.id)}.md</span></div>
      <div id="client-notes-list">${notes}</div>
      <div style="margin-top:12px;border-top:1px dashed var(--border);padding-top:10px;">
        <textarea class="form-textarea" id="client-notes-textarea" placeholder="Añadir nota..."></textarea>
        <div style="display:flex;gap:8px;margin-top:6px;align-items:center;">
          <input class="form-input mono" id="client-notes-tags" placeholder="tags: renewal,qbr" style="flex:1;font-size:13px;padding:5px 10px;">
          <button class="chat-send" id="client-notes-submit" style="margin:0;font-size:13px;padding:6px 16px;">Añadir nota</button>
        </div>
      </div>
    </div>
  `;

  // Wire contact-row clicks via event delegation (avoids onclick attribute injection)
  $$('#client-detail .contact-row').forEach(el => {
    el.addEventListener('click', () => {
      const cid = el.dataset.clientId;
      const idx = parseInt(el.dataset.contactIdx, 10);
      const cli = DATA.clients.find(x => x.id === cid);
      const contact = cli && cli.contacts ? cli.contacts[idx] : null;
      if (contact) openContactEdit(cid, idx, contact);
    });
  });
  // Wire client-detail header buttons (avoid onclick interpolation → XSS-safe)
  const editBtn = $('#client-detail-edit-btn');
  if (editBtn) editBtn.addEventListener('click', () => openEditClient(c.id));
  const contactAddBtn = $('#client-detail-contact-add-btn');
  if (contactAddBtn) contactAddBtn.addEventListener('click', () => openContactAdd(c.id));
  const archiveBtn = $('#client-detail-archive-btn');
  if (archiveBtn) archiveBtn.addEventListener('click', () => openArchiveConfirm('client', c.id));
  // Wire project rows in the client's projects table
  $$('#client-detail .client-project-row').forEach(tr => {
    tr.addEventListener('click', () => {
      const code = tr.dataset.projectCode;
      if (code) { renderProjectDetail(code); goToPage('project-detail'); }
    });
  });

  // Rewire submit for the current client + pull live notes if online
  const clientBtn = $('#client-notes-submit');
  if (clientBtn) {
    clientBtn.onclick = () => submitNote('client', c.id,
      'client-notes-textarea', 'client-notes-tags',
      'client-notes-list', null);
  }
  if (state.online) refreshNotes('client', c.id, 'client-notes-list', null);
}

// ===================== SCHEDULE =====================
// Converts 'YYYY-Www' to ISO-date of that Monday.
function isoWeekToMonday(yyyyWww) {
  const m = /^(\d{4})-W(\d{1,2})$/.exec(yyyyWww);
  if (!m) return null;
  const y = Number(m[1]);
  const w = Number(m[2]);
  // ISO week 1 contains the first Thursday of the year.
  const jan4 = new Date(Date.UTC(y, 0, 4));
  const jan4Dow = jan4.getUTCDay() || 7;  // Sun=0→7
  const week1Monday = new Date(jan4.getTime() - (jan4Dow - 1) * 86400000);
  return new Date(week1Monday.getTime() + (w - 1) * 7 * 86400000);
}

function isoWeekLabel(d) {
  // Returns 'Wnn' from a Date (Monday of that ISO week).
  const target = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
  const dow = target.getUTCDay() || 7;
  target.setUTCDate(target.getUTCDate() + 4 - dow);
  const yearStart = new Date(Date.UTC(target.getUTCFullYear(), 0, 1));
  const weekNo = Math.ceil(((target - yearStart) / 86400000 + 1) / 7);
  return 'W' + String(weekNo).padStart(2, '0');
}

async function buildScheduleHeatmap(startInput, endInput) {
  const startStr = startInput || ($('#sched-start')?.value || '2026-W15');
  const endStr   = endInput   || ($('#sched-end')?.value   || '2026-W18');
  const startMon = isoWeekToMonday(startStr);
  const endMon   = isoWeekToMonday(endStr);
  if (!startMon || !endMon || startMon > endMon) {
    _toast('Rango inválido', 'warn');
    return;
  }

  // Build week labels + Date for fetching the heatmap from backend when online.
  const weeks = [];
  for (let d = new Date(startMon); d <= endMon; d.setUTCDate(d.getUTCDate() + 7)) {
    weeks.push(isoWeekLabel(d));
  }
  const people = Object.keys(DATA.schedule);
  let matrix = {};  // person → [pct per week]

  if (state.online) {
    // Backend heatmap (7 days past endMon to include sunday).
    const sundayOfEnd = new Date(endMon.getTime() + 6 * 86400000);
    const startISO = startMon.toISOString().slice(0, 10);
    const endISO = sundayOfEnd.toISOString().slice(0, 10);
    try {
      const hm = await api.getHeatmap(startISO, endISO);
      matrix = hm.people;
    } catch (err) {
      console.warn('heatmap API failed, falling back to seed', err);
    }
  }
  if (Object.keys(matrix).length === 0) {
    // Offline / fallback — use the seed pattern, repeating modulo its length.
    const seedLen = DATA.scheduleWeeks.length;
    people.forEach(p => {
      matrix[p] = weeks.map((_, i) => DATA.schedule[p][i % seedLen] ?? 0);
    });
  }

  $('#sched-week-count').textContent = `· ${weeks.length} semana${weeks.length === 1 ? '' : 's'}`;

  const el = $('#schedule-heatmap');
  const grid = document.createElement('div');
  grid.className = 'hm-grid';
  grid.style.gridTemplateColumns = `110px repeat(${weeks.length}, minmax(0, 1fr))`;

  let html = '<div class="hm-header"></div>';
  weeks.forEach(w => html += `<div class="hm-header">${w}</div>`);
  Object.keys(matrix).forEach(p => {
    html += `<div class="hm-header" style="justify-content:flex-end;padding-right:10px;font-family:var(--font-mono);">${p}</div>`;
    weeks.forEach((w, i) => {
      const v = matrix[p][i] ?? 0;
      const over = v > 100;
      const label = over
        ? `<span style="color:var(--danger);font-weight:700;">${v}% ⚠</span>`
        : (v ? `${v}%` : '');
      html += `<div class="hm-cell" style="background:${hmColor(v)};" data-person="${p}" data-week="${w}" data-val="${v}">${label}</div>`;
    });
  });
  grid.innerHTML = html;
  el.innerHTML = '';
  el.appendChild(grid);

  grid.querySelectorAll('.hm-cell[data-person]').forEach(cell => {
    cell.addEventListener('mouseenter', (e) => { if (state.scheduleInteraction === 'hover') showSchedulePopover(e, cell); });
    cell.addEventListener('mouseleave', () => { if (state.scheduleInteraction === 'hover') hideSchedulePopover(); });
    cell.addEventListener('click', (e) => { if (state.scheduleInteraction === 'click') showSchedulePopover(e, cell); });
  });
}

function wireScheduleControls() {
  const apply = $('#sched-apply');
  if (apply) apply.addEventListener('click', () => buildScheduleHeatmap());
  // Also rebuild on Enter in either input
  ['#sched-start', '#sched-end'].forEach(sel => {
    const el = $(sel);
    if (el) el.addEventListener('change', () => buildScheduleHeatmap());
  });
}

let _schedulePopover;
function schedulePopover() {
  if (!_schedulePopover) {
    _schedulePopover = document.createElement('div');
    _schedulePopover.className = 'wf-popover';
    _schedulePopover.style.position = 'fixed';
    _schedulePopover.style.zIndex = '9999';
    document.body.appendChild(_schedulePopover);
  }
  return _schedulePopover;
}

function showSchedulePopover(e, cell) {
  const pop = schedulePopover();
  const p = cell.dataset.person, w = cell.dataset.week, v = Number(cell.dataset.val);
  const bd = DATA.scheduleBreakdowns[p] || [];
  const rows = bd.map(b => `
    <div style="display:grid;grid-template-columns:1.6fr 0.5fr 0.9fr 0.5fr;gap:10px;font-size:12px;">
      <span class="mono" style="font-size:11px;">${b.code}</span>
      <span>${b.pct}%</span>
      <span class="text-muted">${b.role}</span>
      <span class="text-muted">${b.h}h</span>
    </div>
  `).join('');
  const over = v > 100 ? `<div style="margin-top:6px;color:var(--danger);font-weight:600;">⚠ Over-allocated ${v}%</div>` : '';
  pop.innerHTML = `
    <div class="fw-600" style="margin-bottom:6px;">${p} · ${w}</div>
    <div class="mono" style="font-size:12px;margin-bottom:6px;">Total: ${v}%</div>
    <div style="display:grid;grid-template-columns:1.6fr 0.5fr 0.9fr 0.5fr;gap:10px;font-family:var(--font-mono);font-size:10px;color:var(--text2);border-bottom:1px dashed var(--border);padding-bottom:4px;margin-bottom:4px;">
      <span>Proyecto</span><span>%</span><span>Rol</span><span>Hrs</span>
    </div>
    ${rows}
    ${over}
  `;
  pop.classList.add('visible');
  const rect = cell.getBoundingClientRect();
  const popW = 280;
  let left = rect.left + rect.width / 2 - popW / 2;
  let top = rect.top - 12;
  if (top < 80) {
    pop.style.transform = '';
    top = rect.bottom + 8;
  } else {
    pop.style.transform = 'translateY(-100%)';
  }
  left = Math.max(8, Math.min(left, window.innerWidth - popW - 8));
  pop.style.left = left + 'px';
  pop.style.top = top + 'px';
  pop.style.width = popW + 'px';
}

function hideSchedulePopover() { if (_schedulePopover) _schedulePopover.classList.remove('visible'); }

// ===================== SKILLS =====================
// Columns come from the live catalog when DATA.skills is populated by
// refreshAll(); rows come from DATA.people[*].skills. Falls back to the
// seed DATA.skillsMatrix when offline.
function buildSkillsMatrix() {
  const tbody = $('#skills-tbody');
  const head = $('#skills-matrix-head');

  let colIds, rowIds, rowFor;

  if (DATA.skills && DATA.people && DATA.people.length) {
    // Live: use catalog (non-archived) as columns and people.skills as source.
    colIds = DATA.skills.filter(s => !s.archived).map(s => s.id);
    rowIds = DATA.people.filter(p => !p.archived).map(p => p.id);
    rowFor = pid => {
      const p = DATA.people.find(x => x.id === pid);
      const map = {};
      (p.skills || []).forEach(s => { map[s.id] = s.lvl; });
      return colIds.map(id => map[id] || 0);
    };
  } else {
    // Seed fallback — uses the short-abbrev catalog shipped with DATA
    const keys = Object.keys(DATA.skillsMatrix.rows);
    colIds = DATA.skillsMatrix.cols;
    rowIds = keys;
    rowFor = pid => DATA.skillsMatrix.rows[pid] || [];
  }

  // Rebuild head: one th per skill, with edit + archive icons
  if (head) {
    const shortFor = id => id.length > 10 ? id.slice(0, 8) + '…' : id;
    head.innerHTML = `
      <th class="row-header"></th>
      ${colIds.map(id => `
        <th data-skill="${id}" title="${id}">
          ${shortFor(id)}
          <span class="skh-edit" title="editar label/desc">✎</span>
          <span class="skh-arch" title="archivar">✕</span>
        </th>
      `).join('')}
    `;
    // Rewire click handlers for the (possibly new) columns
    wireSkillMatrixHeader();
  }

  tbody.innerHTML = rowIds.map(pid => {
    let row = `<td class="row-header">${pid}</td>`;
    rowFor(pid).forEach(v => {
      const color = v === 0 ? 'rgba(30,155,224,0.03)' : `rgba(30,155,224,${v / 5})`;
      row += `<td><div class="skill-cell" style="background:${color};">${v || '—'}</div></td>`;
    });
    return `<tr>${row}</tr>`;
  }).join('');

  $('#gap-bars').innerHTML = (DATA.skillGaps || []).map(g => `
    <div style="display:flex;align-items:center;gap:12px;">
      <span class="mono" style="font-size:12px;min-width:200px;">${g.skill}</span>
      <div style="flex:1;height:20px;background:var(--bg);border-radius:3px;overflow:hidden;position:relative;border:1px dashed var(--border);">
        <div style="width:${(g.have / g.need) * 100}%;height:100%;background:rgba(30,155,224,0.4);border-radius:3px;"></div>
        <div style="position:absolute;right:6px;top:2px;font-size:11px;font-family:var(--font-mono);color:var(--text);">${g.have}/${g.need}</div>
      </div>
      <span class="wf-badge ${g.severity}">-${g.deficit}</span>
    </div>
  `).join('');
}

function wireSkillsTabs() {
  $$('#skills-tabs .tab').forEach(t => {
    t.addEventListener('click', () => {
      $$('#skills-tabs .tab').forEach(x => x.classList.remove('active'));
      t.classList.add('active');
      const v = t.dataset.view;
      $('#skills-matrix-view').style.display = v === 'matrix' ? '' : 'none';
      $('#skills-gap-view').style.display = v === 'gap' ? '' : 'none';
    });
  });
}

// ===================== MAP (MapLibre GL + OSM raster) =====================
// Lazy-init on first visit to /map (MapLibre requires a visible container to
// render correctly). Markers come from /api/geo when online, seed offices when
// offline. Click marker → popup with people IDs + link to People page.
let _mapInstance = null;
let _mapMarkers = [];

function _waitForMapLibre(cb, tries = 40) {
  if (window.maplibregl) return cb();
  if (tries <= 0) { console.warn('maplibre-gl no cargó'); return; }
  setTimeout(() => _waitForMapLibre(cb, tries - 1), 100);
}

function initMap() {
  if (_mapInstance) { _mapInstance.resize(); return; }
  _waitForMapLibre(() => {
    _mapInstance = new maplibregl.Map({
      container: 'maplibre',
      style: {
        version: 8,
        sources: {
          osm: {
            type: 'raster',
            tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
            tileSize: 256,
            attribution: '© <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors',
          },
        },
        layers: [{ id: 'osm', type: 'raster', source: 'osm', minzoom: 0, maxzoom: 19 }],
      },
      center: [-3.7038, 40.4168],  // Madrid default
      zoom: 4,
    });
    _mapInstance.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
    _mapInstance.on('load', () => drawMapMarkers());
  });
}

function drawMapMarkers() {
  if (!_mapInstance) return;
  // Clear previous markers
  _mapMarkers.forEach(m => m.remove());
  _mapMarkers = [];

  const offices = DATA.geo || [];
  // Filter out "remote" / archived / zero-coord offices from map plot
  const plottable = offices.filter(o => !o.archived && (o.lat || o.lon));
  if (plottable.length === 0) {
    // Still center on Madrid; no markers to add
    return;
  }

  const bounds = new maplibregl.LngLatBounds();
  plottable.forEach(o => {
    const el = document.createElement('div');
    el.className = 'ml-marker';
    el.textContent = String((o.people || []).length);
    el.title = `${o.city} — ${(o.people || []).length} persona(s)`;

    const popup = new maplibregl.Popup({ offset: 24, closeButton: true })
      .setHTML(`
        <div style="font-weight:600;margin-bottom:6px;">${o.city}${o.country ? ' · ' + o.country : ''}</div>
        <div class="small text-muted" style="margin-bottom:8px;">${(o.people || []).length} persona(s) · ${o.office_id}</div>
        ${(o.people || []).length
          ? (o.people || []).map(p => `<div class="mono" style="font-size:12px;padding:2px 0;">${p}</div>`).join('')
          : '<div class="text-muted small">Sin personas asignadas a esta oficina</div>'}
        <div style="margin-top:10px;border-top:1px dashed var(--border);padding-top:6px;">
          <a href="#" onclick="goToPage('people');return false;" style="font-size:12px;">Ver en People →</a>
        </div>
      `);

    const marker = new maplibregl.Marker({ element: el })
      .setLngLat([o.lon, o.lat])
      .setPopup(popup)
      .addTo(_mapInstance);

    _mapMarkers.push(marker);
    bounds.extend([o.lon, o.lat]);
  });

  if (plottable.length > 1) {
    _mapInstance.fitBounds(bounds, { padding: 60, maxZoom: 8, duration: 0 });
  } else {
    _mapInstance.flyTo({ center: [plottable[0].lon, plottable[0].lat], zoom: 6, duration: 0 });
  }
}

// Called from renderAll() — refreshes markers if the map already exists
function renderMapMarkers() {
  if (_mapInstance && _mapInstance.loaded()) drawMapMarkers();
}

function wireMap() {
  // MapLibre needs the container to be visible + sized. Init lazily when the
  // user navigates to the page for the first time.
}

// ===================== JOURNAL =====================
// Uses the live API when configured, falls back to DATA.journal otherwise.
// Entries come from the backend as {id, timestamp, proposer, kind, payload_json, status, applied_at, applied_by, rejected_reason}.
// We normalize to the shape the template expects (title, ago, body).

function _jTitle(e) {
  // Derive a human-readable title from kind+payload; payload is JSON in live data.
  let payload = e.payload;
  if (typeof e.payload_json === 'string') {
    try { payload = JSON.parse(e.payload_json); } catch { payload = {}; }
  }
  payload = payload || {};
  const k = e.kind;
  if (k === 'assign')        return `${payload.person_id} → ${payload.project_code}, ${payload.dedication_pct}%, ${payload.role || 'executor'}`;
  if (k === 'unassign')      return `${payload.person_id} ✕ ${payload.project_code}`;
  if (k === 'availability')  return `${payload.person_id}: ${payload.availability_kind} ${payload.start}→${payload.end}, ${payload.pct}%`;
  if (k === 'skill_update')  return `${payload.person_id}: ${payload.skill_id} → L${payload.level}`;
  if (k.startsWith('person_'))  return `${payload.id || ''} ${k}`;
  if (k.startsWith('project_')) return `${payload.code || ''} ${k}`;
  if (k.startsWith('client_'))  return `${payload.id || ''} ${k}`;
  if (k === 'skill_label_update') return `${payload.skill_id} label/desc`;
  return e.title || k;
}
function _jAgo(e) {
  if (e.ago) return e.ago;
  if (!e.timestamp) return '';
  const ms = Date.now() - new Date(e.timestamp).getTime();
  const h = Math.round(ms / 36e5);
  if (h < 1) return 'hace <1h';
  if (h < 24) return `hace ${h}h`;
  return `hace ${Math.round(h / 24)}d`;
}
function _jBody(e) {
  if (e.body) return e.body;
  if (e.status === 'rejected' && e.rejected_reason) return `razón: ${e.rejected_reason}`;
  if (e.status === 'applied' && e.applied_at) return `applied ${e.applied_at}`;
  return '';
}

async function _fetchJournal(status) {
  if (state.online) {
    try {
      const rows = await api.getJournal(status);
      return rows.map(r => ({ ...r, _title: _jTitle(r), _ago: _jAgo(r), _body: _jBody(r) }));
    } catch (err) {
      console.warn('journal fetch failed, falling back to seed', err);
    }
  }
  return DATA.journal.filter(j => j.status === status)
    .map(j => ({ ...j, _title: j.title, _ago: j.ago, _body: j.body }));
}

async function renderJournal(filter = 'pending') {
  const entries = await _fetchJournal(filter);
  const H = _escapeHtml;
  if (entries.length === 0) {
    $('#journal-entries').innerHTML = `<div class="wf-placeholder" style="min-height:120px;">No hay entradas con status "${H(filter)}"</div>`;
    return;
  }
  $('#journal-entries').innerHTML = entries.map(j => `
    <div class="journal-entry ${j.status !== 'pending' ? 'muted' : ''}">
      <div class="je-side">
        <span class="wf-badge ${j.status === 'pending' ? 'amber' : j.status === 'applied' ? 'green' : 'rose'}">${H(j.status)}</span>
        <span class="mono" style="font-size:10px;">${H(j.proposer)}</span>
      </div>
      <div class="je-body">
        <div class="je-title">
          <span class="mono text-muted" style="font-size:11px;">${H(j.kind)}</span>
          ${H(j._title)}
        </div>
        <div class="je-meta">
          ${j._body ? H(j._body) + '<br>' : ''}
          <span class="mono" style="font-size:10px;">${H(j.id)} · ${H(j._ago)}</span>
        </div>
      </div>
      <div class="je-actions">
        ${j.status === 'pending'
          ? `<button class="btn primary small je-apply" data-entry-id="${H(j.id)}">✓ Aplicar</button>
             <button class="btn danger small je-reject" data-entry-id="${H(j.id)}" data-entry-label="${H(j.kind + ' · ' + (j._title || '') + ' · ' + j.id)}">✗ Rechazar</button>`
          : ''}
      </div>
    </div>
  `).join('');
  $$('#journal-entries .je-apply').forEach(b => b.addEventListener('click', () => applyJournal(b.dataset.entryId)));
  $$('#journal-entries .je-reject').forEach(b => b.addEventListener('click', () => openRejectDialog(b.dataset.entryLabel, b.dataset.entryId)));
}

async function applyJournal(id) {
  if (state.online) {
    try {
      await api.applyJournal(id);
      await refreshAll();  // pick up the mutated YAML
      return;
    } catch (err) {
      _toast(`apply falló: ${err.message}\n${err.body || ''}`, 'error');
      return;
    }
  }
  const e = DATA.journal.find(x => x.id === id);
  if (e) { e.status = 'applied'; e.body = 'applied just now'; renderJournal('pending'); }
}

function _activeJournalFilter() {
  const active = document.querySelector('#journal-tabs .tab.active');
  return active ? active.dataset.filter : 'pending';
}

function wireJournalTabs() {
  $$('#journal-tabs .tab').forEach(t => {
    t.addEventListener('click', () => {
      $$('#journal-tabs .tab').forEach(x => x.classList.remove('active'));
      t.classList.add('active');
      renderJournal(t.dataset.filter);
    });
  });
}

// ===================== IDENTITY + SESSION =====================
// Authentication lives in the Authelia cookie (nginx forward-auth). On page
// load we call /api/auth/me to learn who we are, paint the identity block in
// the sidebar, and wire the logout link. If the call fails with 401 the user
// just lost their session — reload lets nginx redirect through login.*. If
// 403 the user exists in Authelia but not in the app's user table — show a
// dedicated "no access" overlay with the logout affordance.

function paintIdentity(me) {
  const badge = document.getElementById('team-badge');
  const nameEl = document.getElementById('sidebar-user-name');
  const roleEl = document.getElementById('sidebar-user-role');
  const logoutA = document.getElementById('logout-link');
  const logoutA2 = document.getElementById('no-access-logout');

  if (!me || typeof me !== 'object') {
    showNoAccessOverlay('Respuesta de /api/auth/me inválida.');
    return;
  }
  const team = me.team || {};
  const slug = String(team.slug || '');

  if (badge) {
    badge.textContent = slug.toUpperCase() || '—';
    badge.dataset.team = slug;
    badge.title = String(team.name || '');
  }
  if (nameEl) nameEl.textContent = String(me.display_name || me.username || '—');
  if (roleEl) roleEl.textContent = me.role === 'admin' ? 'admin' : 'miembro';

  // The journal doesn't own the session. Only show a "log out" link if a
  // logout URL was configured (empty by default); otherwise hide it.
  const href = String(me.logout_url || '').trim();
  [logoutA, logoutA2].forEach(el => {
    if (!el) return;
    if (href) {
      el.href = href;
      el.style.display = '';
    } else {
      el.removeAttribute('href');
      el.style.display = 'none';
    }
  });
}

function showNoAccessOverlay(detail) {
  const overlay = document.getElementById('no-access-overlay');
  if (!overlay) return;
  const msg = document.getElementById('no-access-msg');
  if (msg && detail) msg.textContent = detail;
  overlay.classList.remove('hidden');
}

async function bootstrapApp() {
  // Wire api callbacks first so the getMe() itself triggers them on failure
  api.onUnauthenticated = () => {
    // Reload to let nginx forward-auth redirect to Authelia
    window.location.reload();
  };
  api.onForbidden = (detail) => {
    // detail is the raw response body (JSON string with {detail: "..."})
    let msg = null;
    try { msg = JSON.parse(detail).detail; } catch {}
    showNoAccessOverlay(msg);
  };

  try {
    const me = await api.getMe();
    paintIdentity(me);
    state.online = true;
    return true;
  } catch (err) {
    // 401/403 already triggered the callbacks above; anything else is a genuine
    // backend error we surface silently here (user sees empty app).
    console.error('bootstrapApp failed:', err);
    state.online = false;
    return false;
  }
}

// ===================== NOTES (append-only markdown) =====================
function _escapeHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function _escapeRegex(s) {
  return String(s == null ? '' : s).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

const _TOAST_ICONS = { success: '✓', warn: '!', error: '✗', info: 'i' };
const _TOAST_DURATION = { success: 2500, info: 3000, warn: 4000, error: 6000 };

function _toastStack() {
  let s = document.getElementById('toast-stack');
  if (!s) {
    s = document.createElement('div');
    s.id = 'toast-stack';
    s.className = 'toast-stack';
    // Inline fallback for the case the CSS hasn't loaded the .toast-stack
    // rule (e.g. browser served a cached styles.css). Prevents the stack from
    // joining body's flex layout and pushing main content sideways.
    Object.assign(s.style, {
      position: 'fixed',
      bottom: '24px',
      right: '24px',
      zIndex: '10000',
      display: 'flex',
      flexDirection: 'column-reverse',
      gap: '8px',
      pointerEvents: 'none',
      maxWidth: '420px',
    });
    document.body.appendChild(s);
  }
  return s;
}

function _toast(message, kind = 'info', duration) {
  const k = _TOAST_ICONS[kind] ? kind : 'info';
  const dur = duration != null ? duration : _TOAST_DURATION[k];
  const el = document.createElement('div');
  el.className = `toast ${k}`;
  el.innerHTML = `<span class="toast-icon">${_TOAST_ICONS[k]}</span><span class="toast-msg">${_escapeHtml(message)}</span>`;
  const dismiss = () => {
    if (el._dismissed) return;
    el._dismissed = true;
    el.classList.add('dismissing');
    setTimeout(() => el.remove(), 200);
  };
  el.addEventListener('click', dismiss);
  _toastStack().appendChild(el);
  // Force reflow so the slide-in transition runs
  // eslint-disable-next-line no-unused-expressions
  el.offsetHeight;
  el.classList.add('show');
  if (dur > 0) setTimeout(dismiss, dur);
  return el;
}

function _parseTagCsv(raw) {
  if (!raw) return [];
  return raw.replace(/^tags:\s*/i, '').split(',').map(s => s.trim()).filter(Boolean);
}

async function refreshNotes(entityType, entityId, containerId, counterId) {
  const el = document.getElementById(containerId);
  if (!el) return;
  if (!state.online) {
    el.innerHTML = '<div class="text-muted small">Online requerido para cargar notas.</div>';
    return;
  }
  try {
    const notes = await api.getNotes(entityType, entityId);
    if (!notes.length) {
      el.innerHTML = '<div class="text-muted small">Sin notas aún.</div>';
    } else {
      // Backend returns oldest-first; flip so the newest appears on top.
      el.innerHTML = notes.slice().reverse().map(n => `
        <div class="note-item">
          <div class="note-meta">${_escapeHtml(n.timestamp)} | ${_escapeHtml(n.author)}${(n.tags && n.tags.length) ? ' | tags: ' + _escapeHtml(n.tags.join(', ')) : ''}</div>
          <div class="note-body">${_escapeHtml(n.body)}</div>
        </div>
      `).join('');
    }
    if (counterId) {
      const c = document.getElementById(counterId);
      if (c) c.textContent = `${notes.length} nota${notes.length === 1 ? '' : 's'}`;
    }
  } catch (err) {
    el.innerHTML = `<div class="text-danger small">No se pudieron cargar las notas: ${_escapeHtml(err.message)}</div>`;
  }
}

async function submitNote(entityType, entityId, textareaId, tagsId, containerId, counterId) {
  if (!state.online) { _toast('Sin conexión con el servidor: no se pueden añadir notas.', 'warn'); return; }
  const ta = document.getElementById(textareaId);
  const tagsEl = tagsId ? document.getElementById(tagsId) : null;
  if (!ta) return;
  const body = (ta.value || '').trim();
  if (!body) { _toast('La nota no puede estar vacía.', 'warn'); return; }
  const tags = tagsEl ? _parseTagCsv(tagsEl.value) : [];
  try {
    await api.addNote(entityType, entityId, body, tags);
    ta.value = '';
    if (tagsEl) tagsEl.value = '';
    await refreshNotes(entityType, entityId, containerId, counterId);
  } catch (err) {
    _toast(`No se pudo guardar la nota:\n${err.message}\n${err.body || ''}`, 'error');
  }
}

// ===================== REFRESH ALL (live data) =====================
// Pulls every endpoint in parallel, normalizes shapes, mutates DATA in place,
// then re-renders the whole UI. Called on probe success, after journal apply
// and after modal submits so the UI always reflects the source YAML.

async function refreshAll() {
  if (!state.online) return false;
  try {
    const [peopleRaw, projectsRaw, clientsRaw, skillsRaw, skillGapRaw, coherenceRaw, journalRaw, geoRaw] = await Promise.all([
      api.getPeople(),
      api.getProjects(),
      api.getClients(),
      api.getSkills(),
      api.getSkillGap('pipeline'),
      api.getCoherence(),
      api.getJournal(),
      api.getGeo(),
    ]);

    DATA.people   = peopleRaw.map(api.normalizePerson);
    DATA.projects = projectsRaw.map(api.normalizeProject);
    DATA.clients  = clientsRaw.map(api.normalizeClient);
    DATA.skills   = skillsRaw;  // catalog used by matrix columns

    DATA.skillGaps = (skillGapRaw || []).map(g => ({
      skill: g.skill_id, need: g.need, have: g.have,
      deficit: g.deficit, severity: g.severity,
    }));

    DATA.coherenceWarnings = (coherenceRaw.warnings || []).map(w => ({
      person: w.person_id, rule: w.rule, detail: w.detail, severity: w.severity,
    }));

    DATA.journal = api.normalizeJournal(journalRaw);
    DATA.recentJournal = DATA.journal.slice(0, 3).map(j => ({
      status: j.status, kind: j.kind,
      text: _jTitle(j), ago: _jAgo(j),
    }));

    DATA.geo = geoRaw;

    // Derived fields that the frontend needs but no single endpoint provides:
    // 1) load + assignments per person, derived from /api/projects
    //    (the /api/people list endpoint omits assignments; cross-reference here)
    const loadByPerson = {};
    const assignmentsByPerson = {};
    DATA.projects.forEach(pr => {
      (pr._raw_assignments || []).forEach(a => {
        if (a.archived) return;
        loadByPerson[a.person_id] = (loadByPerson[a.person_id] || 0) + (a.dedication_pct || 0);
        if (!assignmentsByPerson[a.person_id]) assignmentsByPerson[a.person_id] = [];
        assignmentsByPerson[a.person_id].push({
          project: a.project_code,
          role: a.role || 'executor',
          pct: a.dedication_pct || 0,
          window: (a.start && a.end) ? `${a.start} → ${a.end}` : (a.start || a.end || ''),
          start: a.start || null,
          end: a.end || null,
        });
      });
    });
    DATA.people.forEach(p => {
      p.load = loadByPerson[p.id] || 0;
      p.assignments = assignmentsByPerson[p.id] || [];
    });

    // 2) client name ↔ alias map for project/client display
    const clientName = Object.fromEntries(DATA.clients.map(c => [c.id, c.name]));
    DATA.projects.forEach(pr => { pr.client = clientName[pr.client] || pr.client; });

    // 3) warning flag on person from coherence warnings
    DATA.coherenceWarnings.forEach(w => {
      const person = DATA.people.find(p => p.id === w.person);
      if (person) person.warning = w.rule;
    });

    // 4) coverage per project (naive: % of required_skills satisfied by any person ≥ min_level)
    DATA.projects.forEach(pr => {
      if (!pr.required_skills || pr.required_skills.length === 0) {
        pr.coverage = null;
        return;
      }
      let satisfied = 0;
      pr.required_skills.forEach(rs => {
        const anyone = DATA.people.some(p =>
          p.skills.some(s => s.id === rs.skill_id && s.lvl >= rs.min_level)
        );
        if (anyone) satisfied += 1;
      });
      pr.coverage = Math.round((satisfied / pr.required_skills.length) * 100);
    });

    // 5) coverage mirror into each client's embedded projects list
    DATA.clients.forEach(c => {
      c.projects.forEach(cp => {
        const live = DATA.projects.find(p => p.code === cp.code);
        if (live) cp.coverage = live.coverage;
      });
    });

    // 6) overview heatmap matrix — fetch a 26-week window from today
    try {
      const today = new Date();
      const end = new Date(today.getTime() + 26 * 7 * 86400000);
      const hm = await api.getHeatmap(today.toISOString().slice(0, 10), end.toISOString().slice(0, 10));
      state._overviewMatrix = hm.people;
    } catch (err) {
      console.warn('heatmap live fetch failed, staying on seed patterns', err);
    }

    renderAll();
    return true;
  } catch (err) {
    console.warn('refreshAll failed', err);
    return false;
  }
}

function renderOverviewKPIs() {
  const people = (DATA.people || []).filter(p => !p.archived);
  const projects = (DATA.projects || []).filter(p => !p.archived);
  const active = projects.filter(p => p.status === 'active').length;
  const pipeline = projects.filter(p => p.status === 'pipeline').length;
  const warnings = (DATA.coherenceWarnings || []).length;
  const loads = people.map(p => Number(p.load) || 0);
  const avgLoad = loads.length ? Math.round(loads.reduce((a, b) => a + b, 0) / loads.length) : 0;

  const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
  set('kpi-people', String(people.length));
  set('kpi-projects-active', String(active));
  set('kpi-projects-pipeline', String(pipeline));
  set('kpi-coherence-warnings', String(warnings));
  set('kpi-avg-load', `${avgLoad}%`);
}

function renderAll() {
  // Re-render everything that draws from DATA. Popovers/modals don't need it —
  // they re-open fresh each time the user triggers them.
  try { renderOverviewKPIs(); } catch {}
  try { buildOverviewRangeButtons(); buildOverviewHeatmap(state.overviewWeeks); } catch {}
  try { renderOverviewGaps(); renderOverviewWarnings(); renderOverviewJournal(); } catch {}
  try { renderPeopleTable(); } catch {}
  try { renderProjects(); } catch {}
  try { renderClients(); } catch {}
  try { buildSkillsMatrix(); } catch {}
  try { buildScheduleHeatmap(); } catch {}
  try { renderMapMarkers(); } catch {}
  if (state.currentPage === 'journal') renderJournal(_activeJournalFilter());
  // Re-render detail pages if the user is currently looking at one — otherwise
  // mutations (assign/unassign, edits, archive) don't refresh until navigation.
  if (state.currentPage === 'project-detail' && state._editingProject) {
    try { renderProjectDetail(state._editingProject); } catch {}
  }
  if (state.currentPage === 'person-detail' && state._currentPerson) {
    const p = (DATA.people || []).find(x => x.id === state._currentPerson);
    if (p) try { renderPersonDetail(p); } catch {}
  }
}

// (Tweaks panel removed — auth config lives in Authelia, UI knobs moved to
//  per-page controls. Only the identity/logout affordances remain.)

// ===================== INIT =====================
document.addEventListener('DOMContentLoaded', async () => {
  buildOverviewRangeButtons();
  buildOverviewHeatmap(4);
  renderOverviewGaps();
  renderOverviewWarnings();
  renderOverviewJournal();

  renderPeopleTable();
  if (DATA.people.length > 0) renderPersonDetail(DATA.people[0]);

  renderProjects();
  wireProjectTabs();

  renderClients();

  buildScheduleHeatmap();
  wireScheduleControls();

  buildSkillsMatrix();
  wireSkillsTabs();

  wireMap();

  wireJournalTabs();

  // Close popovers when clicking outside
  document.addEventListener('scroll', hideSchedulePopover, true);

  // Identity first — paints team badge, display name, logout link.
  // If the user isn't registered in the app, this shows the no-access overlay
  // and the rest of the UI is still rendered but will read empty data.
  await bootstrapApp();
  if (state.online) {
    try { await refreshAll(); } catch {}
  }
  renderJournal('pending');
});

// =====================================================================
// MODAL HANDLERS (CRUD flows that produce journal pending entries)
// =====================================================================
// Each handler builds a typed payload and POSTs to /api/journal when online,
// or stores to a local _inbox for demo mode (which users can review in the
// Journal page but cannot "apply" — there's no backend to mutate).

async function _submitJournal(kind, payload, closeModalId, opts = {}) {
  const autoApply = !!opts.autoApply;
  if (!state.online) {
    _toast('Sin conexión con el servidor: la propuesta no se puede registrar en el journal.', 'warn');
    return false;
  }
  try {
    const entry = await api.createJournal(kind, payload);
    if (autoApply && entry && entry.id) {
      await api.applyJournal(entry.id);
    }
    if (closeModalId) closeModal(closeModalId);
    await refreshAll();
    _toast(autoApply ? `Entry creada y aplicada.` : `Entry creada. Aplicar desde /journal.`, 'success');
    return true;
  } catch (err) {
    _toast(`No se pudo crear la entry:\n${err.message}\n${err.body || ''}`, 'error');
    return false;
  }
}

// ---------- New Client ----------
function wireNewClientModal() {
  $('#nc-submit').addEventListener('click', async () => {
    const payload = {
      id: $('#nc-id').value.trim().toLowerCase(),
      name: $('#nc-name').value.trim(),
      sector: $('#nc-sector').value.trim(),
      size: $('#nc-size').value,
      country: $('#nc-country').value.trim().toUpperCase(),
      description: $('#nc-desc').value.trim(),
    };
    if (!payload.id || !payload.name) { _toast('ID y Nombre son obligatorios', 'warn'); return; }
    await _submitJournal('client_create', payload, 'new-client-modal', { autoApply: true });
  });
}

// ---------- New Person ----------
function openNewPersonModal() {
  // Reset inputs to defaults so reapertura no arrastra valores previos
  $('#npe-id').value = '';
  $('#npe-name').value = '';
  $('#npe-office').value = 'madrid';
  $('#npe-level').value = 'junior';
  $('#npe-fte').value = '1.0';
  if (!$('#npe-start').value) $('#npe-start').value = new Date().toISOString().slice(0, 10);
  openModal('new-person-modal');
}

function wireNewPersonModal() {
  const btn = $('#npe-submit');
  if (!btn) return;
  btn.addEventListener('click', async () => {
    const payload = {
      id: $('#npe-id').value.trim().toLowerCase(),
      full_name: $('#npe-name').value.trim(),
      office: $('#npe-office').value.trim().toLowerCase(),
      global_level: $('#npe-level').value,
      contractual_fte: Number($('#npe-fte').value) || 1.0,
      start_date: $('#npe-start').value,
    };
    if (!payload.id || !payload.full_name) { _toast('ID y Nombre son obligatorios', 'warn'); return; }
    if (!payload.start_date) { _toast('Start date es obligatorio', 'warn'); return; }
    await _submitJournal('person_create', payload, 'new-person-modal', { autoApply: true });
  });
}

// ---------- New Project ----------
function _renderNprSkillRows(rows) {
  const opts = _SKILL_CATALOG.map(s => `<option value="${s}">${s}</option>`).join('');
  const container = $('#npr-skills-rows');
  if (!container) return;
  if (rows.length === 0) {
    container.innerHTML = '<div class="small text-muted">Sin skills requeridas — usa "+ Añadir skill".</div>';
  } else {
    container.innerHTML = rows.map((r, i) => `
      <div class="nps-row" data-i="${i}" style="display:grid;grid-template-columns:2fr 0.7fr 0.7fr auto;gap:8px;align-items:center;">
        <select class="form-select nps-skill">${opts}</select>
        <input class="form-input mono nps-weight" type="number" min="1" max="3" value="${r.weight || 2}" title="weight 1-3">
        <input class="form-input mono nps-min" type="number" min="1" max="5" value="${r.min_level || 3}" title="min_level 1-5">
        <button type="button" class="btn small danger nps-remove" data-i="${i}">✕</button>
      </div>
    `).join('');
    rows.forEach((r, i) => {
      const rowEl = container.querySelector(`.nps-row[data-i="${i}"]`);
      if (rowEl) rowEl.querySelector('.nps-skill').value = r.skill_id;
    });
    container.querySelectorAll('.nps-remove').forEach(b => {
      b.addEventListener('click', () => {
        _collectNprSkillRows();
        state._npsRows.splice(Number(b.dataset.i), 1);
        _renderNprSkillRows(state._npsRows);
      });
    });
  }
  state._npsRows = rows.slice();
}

function _collectNprSkillRows() {
  const rows = [];
  $$('#npr-skills-rows .nps-row').forEach(el => {
    rows.push({
      skill_id: el.querySelector('.nps-skill').value,
      weight: Number(el.querySelector('.nps-weight').value) || 2,
      min_level: Number(el.querySelector('.nps-min').value) || 3,
    });
  });
  state._npsRows = rows;
  return rows;
}

function openNewProjectModal() {
  const sel = $('#npr-client');
  if (sel) {
    sel.innerHTML = (DATA.clients || []).map(c => `<option value="${c.id}">${c.id} — ${c.name}</option>`).join('');
    if (!sel.options.length) {
      sel.innerHTML = '<option value="">— sin clientes —</option>';
    }
  }
  $('#npr-code').value = '';
  $('#npr-type').value = 'pentest_web';
  $('#npr-status').value = 'pipeline';
  $('#npr-hours').value = '0';
  state._npsRows = [];
  _renderNprSkillRows([]);
  openModal('new-project-modal');
}

// ---------- New Availability ----------
function openNewAvailModal() {
  const personId = state._currentPerson || (state.drawerPerson && state.drawerPerson.id);
  if (!personId) { _toast('Abre primero el detalle de una persona', 'warn'); return; }
  state._navPerson = personId;
  $('#nav-person-display').textContent = personId;
  $('#nav-kind').value = 'pto';
  $('#nav-pct').value = '100';
  const today = new Date();
  const inAWeek = new Date(today.getTime() + 7 * 86400000);
  $('#nav-start').value = today.toISOString().slice(0, 10);
  $('#nav-end').value = inAWeek.toISOString().slice(0, 10);
  $('#nav-reason').value = '';
  openModal('new-avail-modal');
}

function wireNewAvailModal() {
  const btn = $('#nav-submit');
  if (!btn) return;
  btn.addEventListener('click', async () => {
    const payload = {
      person_id: state._navPerson,
      availability_kind: $('#nav-kind').value,
      start: $('#nav-start').value,
      end: $('#nav-end').value,
      pct: Number($('#nav-pct').value) || 100,
      reason: $('#nav-reason').value.trim(),
    };
    if (!payload.person_id) { _toast('Persona no seleccionada', 'warn'); return; }
    if (!payload.start || !payload.end) { _toast('Inicio y Fin son obligatorios', 'warn'); return; }
    if (payload.start > payload.end) { _toast('Inicio debe ser ≤ Fin', 'warn'); return; }
    await _submitJournal('availability', payload, 'new-avail-modal', { autoApply: true });
  });
}

function wireNewProjectModal() {
  const btn = $('#npr-submit');
  if (!btn) return;
  const addBtn = $('#npr-skills-add');
  if (addBtn) {
    addBtn.addEventListener('click', () => {
      _collectNprSkillRows();
      state._npsRows.push({ skill_id: _SKILL_CATALOG[0], weight: 2, min_level: 3 });
      _renderNprSkillRows(state._npsRows);
    });
  }
  btn.addEventListener('click', async () => {
    const required_skills = _collectNprSkillRows();
    // Dedup by skill_id (last wins)
    const seen = new Map();
    required_skills.forEach(r => seen.set(r.skill_id, r));
    const payload = {
      code: $('#npr-code').value.trim(),
      client_alias: $('#npr-client').value.trim().toLowerCase(),
      type: $('#npr-type').value,
      status: $('#npr-status').value,
      window_start: $('#npr-start').value,
      window_end: $('#npr-end').value,
      estimated_hours: Number($('#npr-hours').value) || 0,
      required_skills: Array.from(seen.values()),
    };
    if (!payload.code || !payload.client_alias || !payload.type) {
      _toast('Código, Cliente y Tipo son obligatorios', 'warn'); return;
    }
    if (!payload.window_start || !payload.window_end) {
      _toast('Inicio y Fin son obligatorios', 'warn'); return;
    }
    await _submitJournal('project_create', payload, 'new-project-modal', { autoApply: true });
  });
}

// ---------- Propose Assignment ----------
function openProposeAssignment(projectCode) {
  state._paProject = projectCode;
  $('#pa-project').textContent = projectCode;
  // Populate person select
  const sel = $('#pa-person');
  sel.innerHTML = DATA.people.map(p => `<option value="${p.id}">${p.id} — ${p.name}</option>`).join('');
  // Default dates: today +30 days
  const today = new Date();
  const in30 = new Date(today.getTime() + 30 * 86400000);
  $('#pa-start').value = today.toISOString().slice(0, 10);
  $('#pa-end').value = in30.toISOString().slice(0, 10);
  $('#pa-pct').value = 50;
  openModal('propose-assign-modal');
}

function wireProposeAssignModal() {
  $('#pa-submit').addEventListener('click', async () => {
    const payload = {
      person_id: $('#pa-person').value,
      project_code: state._paProject,
      dedication_pct: Number($('#pa-pct').value),
      start: $('#pa-start').value,
      end: $('#pa-end').value,
      role: $('#pa-role').value,
    };
    if (!payload.person_id || !payload.start || !payload.end) { _toast('Persona y fechas son obligatorios', 'warn'); return; }
    await _submitJournal('assign', payload, 'propose-assign-modal');
  });
}

// ---------- Unassign confirm ----------
function openUnassignConfirm(personId, projectCode) {
  if (!personId || !projectCode) { _toast('Faltan datos para desasignar', 'warn'); return; }
  state._unassignPerson = personId;
  state._unassignProject = projectCode;
  $('#un-person-display').textContent = personId;
  $('#un-project-display').textContent = projectCode;
  openModal('unassign-modal');
}

function wireUnassignModal() {
  const btn = $('#un-submit');
  if (!btn) return;
  btn.addEventListener('click', async () => {
    const payload = { person_id: state._unassignPerson, project_code: state._unassignProject };
    if (!payload.person_id || !payload.project_code) { _toast('Faltan datos', 'warn'); return; }
    await _submitJournal('unassign', payload, 'unassign-modal', { autoApply: true });
  });
}

// ---------- Archive confirm (generic) ----------
function openArchiveConfirm(entityType, entityId) {
  // entityType ∈ {person, project, client, office}
  state._archiveType = entityType;
  state._archiveId = entityId;
  $('#ac-entity-type').textContent = entityType;
  $('#ac-entity-id').textContent = entityId;
  openModal('archive-modal');
}

function wireArchiveModal() {
  $('#ac-submit').addEventListener('click', async () => {
    const type = state._archiveType;
    const id = state._archiveId;
    const kind = `${type}_archive`;
    const payload = type === 'project' ? { code: id, archived: true }
                   : type === 'office'  ? { office_id: id, archived: true }
                   : { id, archived: true };
    await _submitJournal(kind, payload, 'archive-modal');
  });
}

// ---------- Contact add / edit / remove ----------
function openContactAdd(clientId) {
  state._cmMode = 'add';
  state._cmClient = clientId;
  state._cmIdx = null;
  $('#cm-mode-title').textContent = 'Añadir contacto';
  $('#cm-client').textContent = clientId;
  $('#cm-name').value = '';
  $('#cm-role').value = '';
  $('#cm-email').value = '';
  $('#cm-phone').value = '';
  $('#cm-remove').style.display = 'none';
  $('#cm-preview').textContent = 'op: contact_add · proposer: human · status: pending';
  openModal('contact-modal');
}

function openContactEdit(clientId, idx, contact) {
  state._cmMode = 'edit';
  state._cmClient = clientId;
  state._cmIdx = idx;
  $('#cm-mode-title').textContent = `Editar contacto #${idx}`;
  $('#cm-client').textContent = clientId;
  $('#cm-name').value = contact.name || '';
  $('#cm-role').value = contact.role || '';
  $('#cm-email').value = contact.email || '';
  $('#cm-phone').value = contact.phone || '';
  $('#cm-remove').style.display = '';
  $('#cm-preview').textContent = 'op: contact_update · proposer: human · status: pending';
  openModal('contact-modal');
}

function wireContactModal() {
  $('#cm-submit').addEventListener('click', async () => {
    const base = {
      client_id: state._cmClient,
      name: $('#cm-name').value.trim(),
      role: $('#cm-role').value.trim(),
      email: $('#cm-email').value.trim(),
      phone: $('#cm-phone').value.trim(),
    };
    if (!base.name) { _toast('Nombre es obligatorio', 'warn'); return; }
    if (state._cmMode === 'add') {
      await _submitJournal('contact_add', base, 'contact-modal');
    } else {
      await _submitJournal('contact_update', { ...base, contact_index: state._cmIdx }, 'contact-modal');
    }
  });
  $('#cm-remove').addEventListener('click', async () => {
    if (!confirm(`Eliminar contacto #${state._cmIdx} de ${state._cmClient}?`)) return;
    await _submitJournal('contact_remove', {
      client_id: state._cmClient, contact_index: state._cmIdx,
    }, 'contact-modal');
  });
}

// ---------- New skill in catalog ----------
function wireNewCatalogSkillModal() {
  const btn = $('#ncs-submit');
  if (!btn) return;
  btn.addEventListener('click', async () => {
    const id = $('#ncs-id').value.trim().toLowerCase();
    const label = $('#ncs-label').value.trim();
    if (!id || !label) { _toast('ID y label son obligatorios', 'warn'); return; }
    if (!/^[a-z][a-z0-9_]*$/.test(id)) { _toast('ID debe ser snake_case: empieza por letra, solo minúsculas, dígitos, _', 'warn'); return; }
    const payload = { id, label_es: label, description: $('#ncs-desc').value.trim() || undefined };
    await _submitJournal('skill_catalog_create', payload, 'new-catalog-skill-modal');
  });
}

// ---------- Matrix header: archive + edit icons ----------
function wireSkillMatrixHeader() {
  $$('#skills-matrix-head th[data-skill]').forEach(th => {
    const skillId = th.dataset.skill;
    const arch = th.querySelector('.skh-arch');
    const edit = th.querySelector('.skh-edit');
    if (arch) arch.addEventListener('click', async e => {
      e.stopPropagation();
      if (!confirm(`Archivar skill "${skillId}"?\nEntry pending; aplicar en /journal.`)) return;
      await _submitJournal('skill_catalog_archive', { id: skillId, archived: true }, null);
    });
    if (edit) edit.addEventListener('click', e => {
      e.stopPropagation();
      openEditSkillLabel(skillId);
    });
  });
}

// ---------- Person Skill edit ----------
function openEditSkill(personId, existing) {
  state._smPerson = personId;
  $('#sm-person').textContent = personId;
  $('#sm-mode-title').textContent = existing ? `Editar ${existing.skill_id || existing.id}` : 'Añadir skill';
  // Fill skill select with catalog
  const sel = $('#sm-skill');
  // Use DATA skills catalog as source of truth for the dropdown
  const cat = [
    'reconocimiento_externo','osint','hacking_web','bypass_autenticacion','explotacion_logica_negocio',
    'hacking_active_directory','pivoting_movimiento_lateral','escalada_privilegios','explotacion_servicios_red',
    'phishing','ingenieria_social','desarrollo_ofensivo','evasion_defensas','desarrollo_exploits',
    'hacking_cloud','hacking_contenedores','acceso_fisico','evasion_controles_red','reporting','automatizacion_tooling',
  ];
  sel.innerHTML = cat.map(s => `<option value="${s}">${s}</option>`).join('');
  if (existing) {
    sel.value = existing.skill_id || existing.id;
    sel.disabled = true;
    $('#sm-level').value = existing.lvl ?? existing.level ?? 1;
    $('#sm-growth').checked = !!existing.growth;
  } else {
    sel.disabled = false;
    $('#sm-level').value = 1;
    $('#sm-growth').checked = false;
  }
  $('#sm-rationale').value = '';
  openModal('skill-modal');
}

function wireSkillModal() {
  $('#sm-submit').addEventListener('click', async () => {
    const payload = {
      person_id: state._smPerson,
      skill_id: $('#sm-skill').value,
      level: Number($('#sm-level').value),
      growth_interest: $('#sm-growth').checked,
      rationale: $('#sm-rationale').value.trim(),
    };
    await _submitJournal('skill_update', payload, 'skill-modal');
  });
}

// ---------- Edit person (person_update) ----------
function openEditPerson(personId) {
  const p = DATA.people.find(x => x.id === personId);
  if (!p) { _toast(`Persona ${personId} no encontrada`, 'error'); return; }
  state._editingPerson = personId;
  $('#ep-id-display').textContent = personId;
  $('#ep-name').value = p.name || '';
  $('#ep-office').value = (p.office || '').toLowerCase();
  $('#ep-city').value = p.city || '';
  $('#ep-tz').value = p.tz || 'CET';
  $('#ep-langs').value = (p.langs || []).join(',');
  $('#ep-base-role').value = 'pentester';
  $('#ep-level').value = p.level || 'junior';
  $('#ep-fte').value = p.fte ?? 1.0;
  // Snapshot for diff on submit
  state._epOriginal = {
    full_name: p.name, office: (p.office || '').toLowerCase(), city: p.city,
    timezone: p.tz, languages: (p.langs || []).slice(),
    base_role: 'pentester', global_level: p.level, contractual_fte: p.fte,
  };
  openModal('edit-person-modal');
}

function _diffPayload(original, current) {
  const out = {};
  for (const k of Object.keys(current)) {
    const a = original[k], b = current[k];
    const aStr = JSON.stringify(a), bStr = JSON.stringify(b);
    if (aStr !== bStr) out[k] = b;
  }
  return out;
}

function wireEditPersonModal() {
  const btn = $('#ep-submit');
  if (!btn) return;
  btn.addEventListener('click', async () => {
    const current = {
      full_name: $('#ep-name').value.trim(),
      office: $('#ep-office').value,
      city: $('#ep-city').value.trim(),
      timezone: $('#ep-tz').value.trim() || 'CET',
      languages: $('#ep-langs').value.split(',').map(s => s.trim()).filter(Boolean),
      base_role: $('#ep-base-role').value.trim() || 'pentester',
      global_level: $('#ep-level').value,
      contractual_fte: Number($('#ep-fte').value),
    };
    const changed = _diffPayload(state._epOriginal || {}, current);
    if (Object.keys(changed).length === 0) {
      _toast('No hay cambios que guardar.');
      return;
    }
    await _submitJournal('person_update', { id: state._editingPerson, ...changed }, 'edit-person-modal');
  });
}

// ---------- Edit project (project_update) ----------
function openEditProject(code) {
  const pr = DATA.projects.find(x => x.code === code);
  if (!pr) { _toast(`Proyecto ${code} no encontrado`, 'error'); return; }
  state._editingProject = code;
  $('#eproj-code-display').textContent = code;
  // Populate client dropdown
  const sel = $('#eproj-client');
  sel.innerHTML = DATA.clients.map(c => `<option value="${c.id}">${c.id} — ${c.name}</option>`).join('');
  // Best-effort match: seed projects store client name; prefer exact id match if available
  const match = DATA.clients.find(c => pr.client && (pr.client.toLowerCase().includes(c.id) || c.name === pr.client));
  if (match) sel.value = match.id;
  $('#eproj-type').value = pr.type || 'pentest_web';
  // Pre-fill ISO dates from normalizeProject (window_start/end are YYYY-MM-DD)
  $('#eproj-start').value = pr.window_start || '';
  $('#eproj-end').value = pr.window_end || '';
  $('#eproj-hours').value = pr.estimated_hours ?? 0;
  $('#eproj-status').value = pr.status || 'pipeline';
  state._eprojOriginal = {
    client_alias: match ? match.id : null,
    type: pr.type,
    window_start: pr.window_start || null,
    window_end: pr.window_end || null,
    estimated_hours: pr.estimated_hours ?? 0,
    status: pr.status,
  };
  openModal('edit-project-modal');
}

function wireEditProjectModal() {
  const btn = $('#eproj-submit');
  if (!btn) return;
  btn.addEventListener('click', async () => {
    const current = {
      client_alias: $('#eproj-client').value,
      type: $('#eproj-type').value,
      window_start: $('#eproj-start').value || null,
      window_end: $('#eproj-end').value || null,
      estimated_hours: Number($('#eproj-hours').value) || 0,
      status: $('#eproj-status').value,
    };
    const changed = _diffPayload(state._eprojOriginal || {}, current);
    // Drop null values (user left the date blank → no change intended)
    for (const k of Object.keys(changed)) if (changed[k] === null || changed[k] === '') delete changed[k];
    if (Object.keys(changed).length === 0) {
      _toast('No hay cambios que guardar.');
      return;
    }
    await _submitJournal('project_update', { code: state._editingProject, ...changed }, 'edit-project-modal');
  });
}

// ---------- Edit required skills (project_update with required_skills array) ----------
function openRequiredSkills(code) {
  const pr = DATA.projects.find(x => x.code === code);
  state._editingProject = code;
  $('#rs-code-display').textContent = code;
  // Seed with existing required_skills if shipped in DATA, else empty
  // (DATA.projects in frontend doesn't track required_skills; start blank and let user add)
  const existing = pr && pr.required_skills ? pr.required_skills : [];
  _renderReqSkillRows(existing);
  openModal('req-skills-modal');
}

const _SKILL_CATALOG = [
  'reconocimiento_externo','osint','hacking_web','bypass_autenticacion','explotacion_logica_negocio',
  'hacking_active_directory','pivoting_movimiento_lateral','escalada_privilegios','explotacion_servicios_red',
  'phishing','ingenieria_social','desarrollo_ofensivo','evasion_defensas','desarrollo_exploits',
  'hacking_cloud','hacking_contenedores','acceso_fisico','evasion_controles_red','reporting','automatizacion_tooling',
];

function _renderReqSkillRows(rows) {
  const opts = _SKILL_CATALOG.map(s => `<option value="${s}">${s}</option>`).join('');
  const html = rows.length === 0
    ? '<div class="small text-muted">Sin skills requeridas aún — usa "+ Añadir skill requerida".</div>'
    : rows.map((r, i) => `
        <div class="rs-row" data-i="${i}" style="display:grid;grid-template-columns:2fr 0.7fr 0.7fr auto;gap:8px;align-items:center;">
          <select class="form-select rs-skill">${opts}</select>
          <input class="form-input mono rs-weight" type="number" min="1" max="3" value="${r.weight || 2}" title="weight 1-3">
          <input class="form-input mono rs-min" type="number" min="1" max="5" value="${r.min_level || 3}" title="min_level 1-5">
          <button class="btn small danger" onclick="_rsRemoveRow(${i})">✕</button>
        </div>
      `).join('');
  $('#rs-rows').innerHTML = html;
  rows.forEach((r, i) => {
    const rowEl = document.querySelector(`.rs-row[data-i="${i}"]`);
    if (rowEl) rowEl.querySelector('.rs-skill').value = r.skill_id;
  });
  state._rsRows = rows.slice();
}

function _rsRemoveRow(i) {
  _collectReqSkillRows();
  state._rsRows.splice(i, 1);
  _renderReqSkillRows(state._rsRows);
}

function _collectReqSkillRows() {
  const rows = [];
  $$('.rs-row').forEach(el => {
    rows.push({
      skill_id: el.querySelector('.rs-skill').value,
      weight: Number(el.querySelector('.rs-weight').value) || 2,
      min_level: Number(el.querySelector('.rs-min').value) || 3,
    });
  });
  state._rsRows = rows;
  return rows;
}

function wireRequiredSkillsModal() {
  const add = $('#rs-add'), submit = $('#rs-submit');
  if (!add || !submit) return;
  add.addEventListener('click', () => {
    _collectReqSkillRows();
    state._rsRows.push({ skill_id: _SKILL_CATALOG[0], weight: 2, min_level: 3 });
    _renderReqSkillRows(state._rsRows);
  });
  submit.addEventListener('click', async () => {
    const rows = _collectReqSkillRows();
    // Dedup by skill_id (last wins)
    const seen = new Map();
    rows.forEach(r => seen.set(r.skill_id, r));
    const unique = [...seen.values()];
    await _submitJournal('project_update', {
      code: state._editingProject,
      required_skills: unique,
    }, 'req-skills-modal');
  });
}
window._rsRemoveRow = _rsRemoveRow;

// ---------- Edit client (client_update) ----------
function openEditClient(clientId) {
  const c = DATA.clients.find(x => x.id === clientId);
  if (!c) { _toast(`Cliente ${clientId} no encontrado`, 'error'); return; }
  state._editingClient = clientId;
  $('#ec-id-display').textContent = clientId;
  $('#ec-name').value = c.name || '';
  $('#ec-sector').value = c.sector || '';
  $('#ec-size').value = c.size || '';
  $('#ec-country').value = c.country || '';
  $('#ec-desc').value = c.description || '';
  state._ecOriginal = {
    name: c.name, sector: c.sector, size: c.size,
    country: c.country, description: c.description,
  };
  openModal('edit-client-modal');
}

function wireEditClientModal() {
  const btn = $('#ec-submit');
  if (!btn) return;
  btn.addEventListener('click', async () => {
    const current = {
      name: $('#ec-name').value.trim(),
      sector: $('#ec-sector').value.trim(),
      size: $('#ec-size').value,
      country: $('#ec-country').value.trim().toUpperCase(),
      description: $('#ec-desc').value.trim(),
    };
    const changed = _diffPayload(state._ecOriginal || {}, current);
    if (Object.keys(changed).length === 0) {
      _toast('No hay cambios que guardar.');
      return;
    }
    await _submitJournal('client_update', { id: state._editingClient, ...changed }, 'edit-client-modal');
  });
}

// ---------- Edit skill label/description (skill_label_update) ----------
function openEditSkillLabel(skillId) {
  state._editingSkill = skillId;
  $('#esl-id-display').textContent = skillId;
  $('#esl-label').value = '';  // live values unknown offline; user overwrites
  $('#esl-desc').value = '';
  openModal('edit-skill-label-modal');
}

function wireEditSkillLabelModal() {
  const btn = $('#esl-submit');
  if (!btn) return;
  btn.addEventListener('click', async () => {
    const payload = { skill_id: state._editingSkill };
    const label = $('#esl-label').value.trim();
    const desc  = $('#esl-desc').value.trim();
    if (label) payload.label_es = label;
    if (desc)  payload.description = desc;
    if (!label && !desc) { _toast('Nada que cambiar.', 'warn'); return; }
    await _submitJournal('skill_label_update', payload, 'edit-skill-label-modal');
  });
}

// Attach buttons on project/person detail pages that didn't have wiring.
function wireDetailPageButtons() {
  const proposeBtn = $('#proj-propose-assign');
  if (proposeBtn) {
    proposeBtn.addEventListener('click', () => {
      const code = state._editingProject;
      if (!code) { _toast('Abre un proyecto primero', 'warn'); return; }
      openProposeAssignment(code);
    });
  }
  const archiveBtn = $('#proj-archive-btn');
  if (archiveBtn) {
    archiveBtn.addEventListener('click', () => {
      const code = state._editingProject;
      if (!code) { _toast('Abre un proyecto primero', 'warn'); return; }
      openArchiveConfirm('project', code);
    });
  }
  const editBtn = $('#project-detail-edit-btn');
  if (editBtn) {
    editBtn.addEventListener('click', () => {
      const code = state._editingProject;
      if (!code) { _toast('Abre un proyecto primero', 'warn'); return; }
      openEditProject(code);
    });
  }
}

// =====================================================================
// INIT (extension)
// =====================================================================
document.addEventListener('DOMContentLoaded', () => {
  wireNewClientModal();
  wireNewPersonModal();
  wireNewProjectModal();
  wireNewAvailModal();
  wireUnassignModal();
  wirePeopleFilters();
  // KPIs initial paint with empty DATA, then refreshAll repaints
  try { renderOverviewKPIs(); } catch {}
  wireProposeAssignModal();
  wireArchiveModal();
  wireContactModal();
  wireSkillModal();
  wireNewCatalogSkillModal();
  wireSkillMatrixHeader();
  wireEditPersonModal();
  wireEditProjectModal();
  wireEditClientModal();
  wireEditSkillLabelModal();
  wireRequiredSkillsModal();
  wireDetailPageButtons();
  wireSearchInput();
});

// ---------- Search input (live FTS with debounce) ----------
let _searchTimer;

// Read the search aside filters into the shape api.search() expects.
function _readSearchFilters() {
  const types = Array.from(document.querySelectorAll('.search-type'))
    .filter(c => c.checked).map(c => c.value);
  const tags = Array.from(document.querySelectorAll('.search-tag.on'))
    .map(t => t.dataset.tag);
  return {
    types,
    date_from: $('#search-date-from')?.value || '',
    date_to: $('#search-date-to')?.value || '',
    tags,
  };
}

function wireSearchInput() {
  const input = $('#search-input');
  if (!input) return;
  input.disabled = false;
  input.addEventListener('input', () => {
    clearTimeout(_searchTimer);
    _searchTimer = setTimeout(runSearch, 220);
  });

  // Filters: any change re-runs the search.
  document.querySelectorAll('.search-type').forEach(c =>
    c.addEventListener('change', runSearch));
  ['#search-date-from', '#search-date-to'].forEach(sel =>
    $(sel)?.addEventListener('change', runSearch));
  document.querySelectorAll('.search-tag').forEach(tag =>
    tag.addEventListener('click', () => {
      tag.classList.toggle('on');
      tag.style.boxShadow = tag.classList.contains('on') ? '0 0 0 2px var(--accent)' : '';
      runSearch();
    }));
  $('#search-clear')?.addEventListener('click', () => {
    document.querySelectorAll('.search-type').forEach(c => { c.checked = true; });
    document.querySelectorAll('.search-tag.on').forEach(t => {
      t.classList.remove('on'); t.style.boxShadow = '';
    });
    const df = $('#search-date-from'); if (df) df.value = '';
    const dt = $('#search-date-to'); if (dt) dt.value = '';
    runSearch();
  });

  // First fill: render the static pre-set query against the live API if online
  if (state.online) runSearch();
}

async function runSearch() {
  const q = ($('#search-input')?.value || '').trim();
  if (!state.online) return;  // offline uses the static HTML in index.html
  if (!q) return;  // empty query: keep the static placeholder, don't overwrite it
  const target = $('#search-results');
  if (!target) return;
  const H = _escapeHtml;
  try {
    const res = await api.search(q, _readSearchFilters());
    const qEsc = H(q);
    const hl = body => {
      const safe = H((body || '').slice(0, 180));
      if (!qEsc) return safe;
      try {
        return safe.replace(new RegExp(_escapeRegex(qEsc), 'gi'), m => `<mark>${m}</mark>`);
      } catch { return safe; }
    };
    const people = (res.people || []).map(p => `
      <div class="search-result">
        <span class="mono text-accent" style="font-size:12px;">${H(p.id)}</span> — ${H(p.full_name)}
        · <span class="text-muted small">${H(p.office)} · ${H(p.global_level)}</span>
      </div>`).join('');
    const projects = (res.projects || []).map(p => `
      <div class="search-result">
        <span class="mono text-accent" style="font-size:12px;">${H(p.code)}</span>
        · <span class="text-muted small">${H(p.client_alias)} · ${H(p.type)} · ${H(p.status)}</span>
      </div>`).join('');
    const notes = (res.notes || []).map(n => `
      <div class="search-result">
        <span class="mono text-accent" style="font-size:12px;">notes/${H(n.entity_type)}s/${H(n.entity_id)}.md</span><br>
        <span class="text-muted small">${hl(n.body)}</span>
      </div>`).join('');
    target.innerHTML = `
      <div class="search-stats">${res.stats.total} ${res.stats.total === 1 ? 'resultado' : 'resultados'} · índice SQLite FTS5</div>
      ${people ? `<div class="search-group-title">Personas (${res.people.length})</div>${people}` : ''}
      ${projects ? `<div class="search-group-title">Proyectos (${res.projects.length})</div>${projects}` : ''}
      ${notes ? `<div class="search-group-title">Notas (${res.notes.length})</div>${notes}` : ''}
      ${res.stats.total === 0 ? '<div class="wf-placeholder" style="min-height:60px;">Sin resultados</div>' : ''}
    `;
  } catch (err) {
    console.warn('search failed', err);
  }
}

// Expose for inline handlers
window.goToPage = goToPage;
window.openDrawer = openDrawer;
window.closeDrawer = closeDrawer;
window.openModal = openModal;
window.closeModal = closeModal;
window.openRejectDialog = openRejectDialog;
window.confirmReject = confirmReject;
window.renderPersonById = renderPersonById;
window.applyJournal = applyJournal;
window.openProposeAssignment = openProposeAssignment;
window.openArchiveConfirm = openArchiveConfirm;
window.openContactAdd = openContactAdd;
window.openContactEdit = openContactEdit;
window.openEditSkill = openEditSkill;
window.openEditPerson = openEditPerson;
window.openEditProject = openEditProject;
window.openEditClient = openEditClient;
window.openEditSkillLabel = openEditSkillLabel;
window.openRequiredSkills = openRequiredSkills;
window.openNewPersonModal = openNewPersonModal;
window.openNewProjectModal = openNewProjectModal;
window.openNewAvailModal = openNewAvailModal;
window.openUnassignConfirm = openUnassignConfirm;
window.submitNote = submitNote;
window.refreshNotes = refreshNotes;
window.renderProjectDetail = renderProjectDetail;
window.state = state;  // used by inline onclick in header buttons
