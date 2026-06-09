// ===================== API CLIENT =====================
// Same-origin fetch wrapper. Authentication lives in the Authelia session
// cookie set by nginx forward-auth — we don't touch it.
// The frontend calls /api/auth/me first to learn who it's talking for, then
// uses the wrappers below.
//
// Error handling contract:
//   401 -> Authelia cookie expired. Trigger `api.onUnauthenticated` (callback
//          wired by app.js to `window.location.reload()` so nginx redirects
//          back through the Authelia login).
//   403 -> user authenticated in Authelia but not registered in app's user
//          table (or archived). Trigger `api.onForbidden` — app.js paints a
//          full-page "no access" message.
//   other -> thrown as Error with .status set.

const api = {
  // Callbacks set by app.js at init
  onUnauthenticated: null,
  onForbidden: null,

  base() {
    return window.location.origin;
  },

  async request(method, path, body) {
    const url = `${this.base()}/api${path}`;
    const opts = {
      method,
      credentials: 'include',  // carry Authelia cookie
      headers: {},
    };
    if (body !== undefined) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(url, opts);

    if (res.status === 401) {
      if (typeof this.onUnauthenticated === 'function') this.onUnauthenticated();
      throw _apiError(method, path, res, await _bodyText(res));
    }
    if (res.status === 403) {
      const text = await _bodyText(res);
      if (typeof this.onForbidden === 'function') this.onForbidden(text);
      throw _apiError(method, path, res, text);
    }
    if (!res.ok) {
      throw _apiError(method, path, res, await _bodyText(res));
    }
    const ct = res.headers.get('content-type') || '';
    return ct.includes('application/json') ? res.json() : res.text();
  },

  get(path)        { return this.request('GET', path); },
  post(path, body) { return this.request('POST', path, body ?? {}); },
  patch(path, body){ return this.request('PATCH', path, body ?? {}); },

  // ----- Identity -----
  async ping() {
    try {
      const r = await fetch(`${this.base()}/api/health`);
      return r.ok;
    } catch { return false; }
  },
  getMe() { return this.get('/auth/me'); },

  // ----- Business endpoints -----
  getJournal(status)                 { return this.get(`/journal${status ? `?status=${status}` : ''}`); },
  createJournal(kind, payload)       { return this.post('/journal', { kind, payload }); },
  applyJournal(id)                   { return this.post(`/journal/${id}/apply`); },
  rejectJournal(id, reason)          { return this.post(`/journal/${id}/reject`, { reason }); },

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
  search(q, filters = {})            {
    const p = new URLSearchParams({ q });
    if (filters.types && filters.types.length) p.set('types', filters.types.join(','));
    if (filters.date_from) p.set('date_from', filters.date_from);
    if (filters.date_to) p.set('date_to', filters.date_to);
    if (filters.tags && filters.tags.length) p.set('tags', filters.tags.join(','));
    return this.get(`/search?${p.toString()}`);
  },

  getNotes(type, id)                 { return this.get(`/notes?entity_type=${type}&entity_id=${id}`); },
  addNote(type, id, body, tags=[])   { return this.post('/notes', { entity_type: type, entity_id: id, body, tags }); },

  // ----- Admin (role=admin only; endpoint 403s otherwise) -----
  adminListUsers(archived=false)     { return this.get(`/admin/users${archived ? '?archived=true' : ''}`); },
  adminCreateUser(body)              { return this.post('/admin/users', body); },
  adminPatchUser(userId, body)       { return this.patch(`/admin/users/${userId}`, body); },
  adminAuthEvents(params={}) {
    const q = new URLSearchParams(params).toString();
    return this.get(`/admin/auth-events${q ? '?' + q : ''}`);
  },
};

function _bodyText(res) {
  return res.text().catch(() => '');
}

function _apiError(method, path, res, text) {
  const err = new Error(`${method} ${path} → ${res.status} ${res.statusText}`);
  err.status = res.status;
  err.body = text;
  try { err.detail = JSON.parse(text).detail; } catch {}
  return err;
}

// ===================== NORMALIZERS =====================
// Map the backend response shape (pydantic, snake_case, raw ISO dates) into
// the shape that app.js render functions expect.

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
    load: 0,
    warning: null,
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
    notes: [],
  };
};

api.normalizeProject = function(pr) {
  const assigned = (pr.assignments || []).filter(a => !a.archived).length;
  const total = (pr.required_skills || []).length || 1;
  return {
    code: pr.code,
    type: pr.type,
    client: pr.client_alias,
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
      coverage: null,
    })),
    contacts: (c.contacts || []).map(k => ({
      name: k.name, role: k.role, email: k.email, phone: k.phone,
      initials: (k.name || '').split(' ').map(x => x[0]).join('').slice(0, 2).toUpperCase(),
    })),
    notes: [],
  };
};

api.normalizeJournal = function(entries) {
  return entries.map(e => ({
    ...e,
    payload: (() => {
      try { return typeof e.payload_json === 'string' ? JSON.parse(e.payload_json) : (e.payload || {}); }
      catch { return {}; }
    })(),
  }));
};

window.api = api;
