// ===================== API CLIENT =====================
// Thin wrapper around fetch() that injects X-API-Key and resolves the base URL
// from localStorage (set via the Tweaks panel). When `isConfigured()` is false,
// callers fall back to the static DATA seed in data.js.
//
// Storage keys:
//   offsec.apiBase   default "http://localhost:8000"
//   offsec.apiKey    set by user after `make install` reveals it

const STORE = {
  base: 'offsec.apiBase',
  key: 'offsec.apiKey',
};

// When the app is served by FastAPI (same origin), use that. When opened as a
// local file (file://) or from a separate dev server, fall back to :8000.
function _defaultBase() {
  const loc = window.location;
  if (loc.protocol === 'file:') return 'http://localhost:8000';
  // Strip trailing slash and pathname — we only want origin.
  return loc.origin;
}

const api = {
  base() {
    return (localStorage.getItem(STORE.base) || _defaultBase()).replace(/\/$/, '');
  },
  key() {
    return localStorage.getItem(STORE.key) || '';
  },
  setConfig(base, key) {
    if (base != null) localStorage.setItem(STORE.base, base.trim().replace(/\/$/, ''));
    if (key != null) localStorage.setItem(STORE.key, key.trim());
  },
  clearConfig() {
    localStorage.removeItem(STORE.base);
    localStorage.removeItem(STORE.key);
  },
  isConfigured() {
    return !!this.key();
  },

  // Same-origin localhost deployments: backend returns its own API key so the
  // user never has to paste anything. Returns false if the endpoint 403s
  // (non-loopback) or if called from file://.
  async bootstrap() {
    try {
      const r = await fetch(`${this.base()}/api/bootstrap`);
      if (!r.ok) return false;
      const data = await r.json();
      if (!data.api_key) return false;
      this.setConfig(this.base(), data.api_key);
      return true;
    } catch { return false; }
  },

  async request(method, path, body) {
    const url = `${this.base()}/api${path}`;
    const opts = {
      method,
      headers: { 'X-API-Key': this.key() },
    };
    if (body !== undefined) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(url, opts);
    if (!res.ok) {
      const text = await res.text().catch(() => '');
      const err = new Error(`${method} ${path} → ${res.status} ${res.statusText}`);
      err.status = res.status;
      err.body = text;
      throw err;
    }
    const ct = res.headers.get('content-type') || '';
    return ct.includes('application/json') ? res.json() : res.text();
  },

  get(path)        { return this.request('GET', path); },
  post(path, body) { return this.request('POST', path, body ?? {}); },

  // ----- Health probe -----
  async ping() {
    try {
      const r = await fetch(`${this.base()}/api/health`);
      return r.ok;
    } catch { return false; }
  },

  // ----- Convenience wrappers -----
  getJournal(status)                 { return this.get(`/journal${status ? `?status=${status}` : ''}`); },
  createJournal(kind, payload)       { return this.post('/journal', { kind, payload }); },
  applyJournal(id, appliedBy='human'){ return this.post(`/journal/${id}/apply?applied_by=${encodeURIComponent(appliedBy)}`); },
  rejectJournal(id, reason, by='human') { return this.post(`/journal/${id}/reject`, { reason, applied_by: by }); },

  getPeople(archived=false)          { return this.get(`/people${archived ? '?archived=true' : ''}`); },
  getPerson(id)                      { return this.get(`/people/${id}`); },
  getPersonCoherence(id)             { return this.get(`/people/${id}/coherence`); },

  getProjects(status)                { return this.get(`/projects${status ? `?status=${status}` : ''}`); },
  getProject(code)                   { return this.get(`/projects/${code}`); },

  getClients()                       { return this.get('/clients'); },
  getClient(id)                      { return this.get(`/clients/${id}`); },

  getSkills()                        { return this.get('/skills'); },
  getOffices()                       { return this.get('/offices'); },
  getGeo()                           { return this.get('/geo'); },
  getCoherence()                     { return this.get('/coherence'); },
  getSkillGap(scope='pipeline')      { return this.get(`/skill-gap?scope=${scope}`); },
  getHeatmap(start, end)             { return this.get(`/heatmap?start=${start}&end=${end}`); },
  search(q)                          { return this.get(`/search?q=${encodeURIComponent(q)}`); },

  getNotes(type, id)                 { return this.get(`/notes?entity_type=${type}&entity_id=${id}`); },
  addNote(type, id, body, author='human', tags=[]) {
    return this.post('/notes', { entity_type: type, entity_id: id, body, author, tags });
  },
};

// ===================== NORMALIZERS =====================
// Map the backend response shape (pydantic, snake_case, raw ISO dates) into
// the shape that app.js render functions expect (historically DATA.js seed).
// Keeping this boundary thin means render code doesn't need to know whether
// data came from the API or the seed.

function _fmtWindow(start, end) {
  if (!start || !end) return '';
  return `${start} → ${end}`;
}

api.normalizePerson = function(p) {
  return {
    id: p.id,
    name: p.full_name,
    office: p.office,
    city: p.city,
    tz: p.timezone,
    level: p.global_level,
    fte: p.contractual_fte,
    start: p.start_date,
    langs: p.languages || [],
    archived: !!p.archived,
    load: 0,        // filled later by aggregating project assignments
    warning: null,  // filled later by merging coherence warnings
    skills: (p.skills || []).map(s => ({
      id: s.skill_id,
      lvl: s.level,
      last: s.last_used_on_project,
      growth: !!s.growth_interest,
    })),
    assignments: (p.assignments || []).map(a => ({
      project: a.project_code,
      role: a.role,
      pct: a.dedication_pct,
      window: _fmtWindow(a.start, a.end),
    })),
    availability: (p.availability || []).map(a => ({
      kind: a.kind,
      window: _fmtWindow(a.start, a.end),
      pct: a.pct,
      reason: a.reason,
      status: a.archived ? 'archived' : 'applied',
    })),
    coherence: { ok: true, msg: '' },
    notes: [],  // filled per-person via /api/notes
  };
};

api.normalizeProject = function(pr) {
  const assigned = (pr.assignments || []).filter(a => !a.archived).length;
  const total = (pr.required_skills || []).length || 1;
  // Coverage: % of required skills that have at least one team member ≥ min_level.
  // Without the full people list here, we store null and compute after people land.
  return {
    code: pr.code,
    type: pr.type,
    client: pr.client_alias,   // resolved to name when clients are loaded
    window: _fmtWindow(pr.window_start, pr.window_end),
    window_start: pr.window_start,
    window_end: pr.window_end,
    status: pr.status,
    estimated_hours: pr.estimated_hours,
    archived: !!pr.archived,
    coverage: null,
    assigned,
    total,
    required_skills: (pr.required_skills || []).map(r => ({
      skill_id: r.skill_id, weight: r.weight, min_level: r.min_level,
    })),
    _raw_assignments: pr.assignments || [],
  };
};

api.normalizeClient = function(c) {
  return {
    id: c.id,
    name: c.name,
    sector: c.sector,
    size: c.size,
    country: c.country,
    status: c.status || 'activo',
    archived: !!c.archived,
    description: c.description || '',
    projects: (c.projects || []).map(p => ({
      code: p.code,
      type: p.type,
      window: _fmtWindow(p.window_start, p.window_end),
      status: p.status,
      coverage: null,  // computed later
    })),
    contacts: (c.contacts || []).map(k => ({
      name: k.name, role: k.role, email: k.email, phone: k.phone,
      initials: (k.name || '').split(' ').map(x => x[0]).join('').slice(0, 2).toUpperCase(),
    })),
    notes: [],
  };
};

api.normalizeJournal = function(entries) {
  // Entries from /api/journal have payload_json (string); render code can parse on demand.
  return entries.map(e => ({
    ...e,
    payload: (() => {
      try { return typeof e.payload_json === 'string' ? JSON.parse(e.payload_json) : (e.payload || {}); }
      catch { return {}; }
    })(),
  }));
};

window.api = api;
