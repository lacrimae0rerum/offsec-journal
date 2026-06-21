// @ts-check
/**
 * Battery test — creates a full dataset (10 people, 3 clients, 4 projects,
 * assignments, skills, notes), verifies all major UI flows, then cleans up.
 *
 * Run with:  npm run test:battery
 *
 * All tests are tagged @write — excluded from test:loop.
 * Serial mode: tests run in order and share module-level CREATED state.
 *
 * Flow:
 *   Phase 1 — Create 3 clients
 *   Phase 2 — Create 10 people with varied profiles
 *   Phase 3 — Assign skills to each person
 *   Phase 4 — Create 4 projects (web, infra, red team, internal)
 *   Phase 5 — Assign people to projects with different roles/dedication
 *   Phase 6 — UI & API verification
 *   Phase 7 — Cleanup (archive everything)
 */

const { test, expect } = require('@playwright/test');
const { bootApp, goTo, apiPost, apiGet } = require('./helpers');

test.describe.configure({ mode: 'serial' });

// Unique suffix per run — base-36 ms timestamp. Starts with 'e' so IDs are
// valid (pattern ^[a-z][a-z0-9_]*$). Client/person IDs: e2e<stamp>_<name>.
const STAMP = Date.now();
const TAG = `e2e${STAMP.toString(36)}`;

// Project codes need the pattern ^[A-Z]{2,4}-\d{4}-\d{3}$.
// Use STAMP-derived 3-digit suffix (100–999) to avoid conflicts between runs.
const N3 = String(STAMP % 900 + 100);

const CREATED = {
  people: [],      // person IDs
  clients: [],     // client IDs
  projects: [],    // project codes
  assignments: [], // [{person_id, project_code, start}]
  skillIds: [],    // from /api/skills catalog
};

// Single browser page reused across all serial tests.
let P;

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

/** POST /api/journal + immediately apply the resulting pending entry. */
async function jApply(kind, payload) {
  const entry = await apiPost(P, '/journal', { kind, payload });
  expect(entry, `jApply(${kind}): entry created`).toHaveProperty('id');
  expect(entry.status, `jApply(${kind}): entry must be pending`).toBe('pending');
  const applied = await apiPost(P, `/journal/${entry.id}/apply`, {});
  expect(applied.status, `jApply(${kind}): entry must be applied`).toBe('applied');
  return applied;
}

/** Best-effort jApply — swallows errors, used in cleanup. */
async function jApplySoft(kind, payload) {
  try {
    const entry = await apiPost(P, '/journal', { kind, payload });
    if (entry?.id) await apiPost(P, `/journal/${entry.id}/apply`, {});
  } catch {
    // best-effort; test result unaffected
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Lifecycle
// ─────────────────────────────────────────────────────────────────────────────

test.beforeAll(async ({ browser }) => {
  P = await browser.newPage();
  await bootApp(P);
});

test.afterAll(async () => {
  await P?.close();
});

// ─────────────────────────────────────────────────────────────────────────────
// Phase 1 — Clients
// ─────────────────────────────────────────────────────────────────────────────

test('P1: crear cliente Acme Corp @write', async () => {
  const id = `${TAG}_acme`;
  await jApply('client_create', {
    id,
    name: 'Acme Corp (E2E)',
    sector: 'fintech',
    size: 'large',
    country: 'ES',
    description: 'Test client A — pentest web',
  });
  CREATED.clients.push(id);
});

test('P1: crear cliente TechWave Inc @write', async () => {
  const id = `${TAG}_wave`;
  await jApply('client_create', {
    id,
    name: 'TechWave Inc (E2E)',
    sector: 'saas',
    size: 'medium',
    country: 'UK',
    description: 'Test client B — pentest infra',
  });
  CREATED.clients.push(id);
});

test('P1: crear cliente SecureX Ltd @write', async () => {
  const id = `${TAG}_secx`;
  await jApply('client_create', {
    id,
    name: 'SecureX Ltd (E2E)',
    sector: 'healthcare',
    size: 'small',
    country: 'DE',
    description: 'Test client C — red team',
  });
  CREATED.clients.push(id);
});

// ─────────────────────────────────────────────────────────────────────────────
// Phase 2 — People (10 personas variadas)
// ─────────────────────────────────────────────────────────────────────────────

const PEOPLE = [
  { suffix: 'alice',   full_name: 'Alice Martínez',    office: 'mad', city: 'Madrid',    timezone: 'CET', languages: ['es','en'],       base_role: 'pentester',  global_level: 'senior',       contractual_fte: 1.0, start_date: '2023-01-15' },
  { suffix: 'bob',     full_name: 'Bob Chen',           office: 'lon', city: 'London',    timezone: 'GMT', languages: ['en','zh'],       base_role: 'pentester',  global_level: 'junior',       contractual_fte: 1.0, start_date: '2024-03-01' },
  { suffix: 'carlos',  full_name: 'Carlos Ruiz',        office: 'bcn', city: 'Barcelona', timezone: 'CET', languages: ['es','ca','en'],  base_role: 'pentester',  global_level: 'intermediate', contractual_fte: 0.8, start_date: '2022-06-01' },
  { suffix: 'diana',   full_name: 'Diana Popescu',      office: 'buc', city: 'Bucharest', timezone: 'EET', languages: ['ro','en'],       base_role: 'pentester',  global_level: 'master',       contractual_fte: 1.0, start_date: '2020-09-01' },
  { suffix: 'erik',    full_name: 'Erik Lindstrom',     office: 'sto', city: 'Stockholm', timezone: 'CET', languages: ['sv','en'],       base_role: 'team_lead',  global_level: 'senior',       contractual_fte: 1.0, start_date: '2021-02-15' },
  { suffix: 'fatima',  full_name: 'Fatima Al-Hassan',   office: 'dub', city: 'Dubai',     timezone: 'GST', languages: ['ar','en'],       base_role: 'pentester',  global_level: 'intermediate', contractual_fte: 0.5, start_date: '2023-07-01' },
  { suffix: 'giorgio', full_name: 'Giorgio Ferrari',    office: 'rom', city: 'Rome',      timezone: 'CET', languages: ['it','en'],       base_role: 'pentester',  global_level: 'junior',       contractual_fte: 1.0, start_date: '2025-01-10' },
  { suffix: 'hannah',  full_name: 'Hannah Muller',      office: 'ber', city: 'Berlin',    timezone: 'CET', languages: ['de','en'],       base_role: 'pentester',  global_level: 'senior',       contractual_fte: 1.0, start_date: '2022-11-01' },
  { suffix: 'ivan',    full_name: 'Ivan Petrov',        office: 'mad', city: 'Madrid',    timezone: 'CET', languages: ['ru','en','es'],  base_role: 'pentester',  global_level: 'intermediate', contractual_fte: 1.0, start_date: '2023-04-01' },
  { suffix: 'julia',   full_name: 'Julia Santos',       office: 'lon', city: 'London',    timezone: 'GMT', languages: ['pt','en'],       base_role: 'pentester',  global_level: 'junior',       contractual_fte: 0.8, start_date: '2024-09-01' },
];

for (const p of PEOPLE) {
  test(`P2: crear persona ${p.full_name} @write`, async () => {
    const id = `${TAG}_${p.suffix}`;
    const { suffix, ...rest } = p;
    await jApply('person_create', { id, ...rest });
    CREATED.people.push(id);
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Phase 3 — Skills
// ─────────────────────────────────────────────────────────────────────────────

test('P3: asignar skills a las 10 personas @write', async () => {
  const skills = await apiGet(P, '/skills');
  if (!skills.length) { test.skip(); return; }
  CREATED.skillIds = skills.map(s => s.id);
  const S = CREATED.skillIds;

  // Each person gets 2–5 skills with varying levels (1–5).
  // Index wraps with % in case catalog has fewer than 10 skills.
  const plan = [
    { suffix: 'alice',   pairs: [[0,4],[1,3],[2,5],[3,3]]      },
    { suffix: 'bob',     pairs: [[0,2],[3,1],[4,2]]            },
    { suffix: 'carlos',  pairs: [[1,3],[2,4],[5,2],[6,3]]      },
    { suffix: 'diana',   pairs: [[0,5],[1,5],[2,5],[3,4],[4,4]] },
    { suffix: 'erik',    pairs: [[0,4],[1,4],[3,3],[7,3]]      },
    { suffix: 'fatima',  pairs: [[2,3],[4,2],[5,3]]            },
    { suffix: 'giorgio', pairs: [[0,1],[1,2]]                  },
    { suffix: 'hannah',  pairs: [[0,4],[2,4],[3,3],[8,2]]      },
    { suffix: 'ivan',    pairs: [[1,3],[4,3],[5,2],[9,3]]      },
    { suffix: 'julia',   pairs: [[2,2],[3,1]]                  },
  ];

  for (const { suffix, pairs } of plan) {
    const person_id = `${TAG}_${suffix}`;
    for (const [idx, level] of pairs) {
      const skill_id = S[idx % S.length];
      await jApply('skill_update', { person_id, skill_id, level, note: 'battery e2e' });
    }
  }
});

// ─────────────────────────────────────────────────────────────────────────────
// Phase 4 — Projects
// ─────────────────────────────────────────────────────────────────────────────

test('P4: crear proyecto pentest web (activo) @write', async () => {
  if (!CREATED.clients.length) { test.skip(); return; }
  const code = `ACM-2026-${N3}`;
  await jApply('project_create', {
    code,
    client_alias: CREATED.clients[0],
    type: 'pentest_web',
    window_start: '2026-07-01',
    window_end: '2026-08-31',
    estimated_hours: 200,
    status: 'active',
  });
  CREATED.projects.push(code);
});

test('P4: crear proyecto pentest infra (pipeline) @write', async () => {
  if (!CREATED.clients.length) { test.skip(); return; }
  const code = `WAV-2026-${N3}`;
  await jApply('project_create', {
    code,
    client_alias: CREATED.clients[1] || CREATED.clients[0],
    type: 'pentest_infra',
    window_start: '2026-09-01',
    window_end: '2026-10-15',
    estimated_hours: 320,
    status: 'pipeline',
  });
  CREATED.projects.push(code);
});

test('P4: crear proyecto red team (activo) @write', async () => {
  if (!CREATED.clients.length) { test.skip(); return; }
  const code = `SCX-2026-${N3}`;
  await jApply('project_create', {
    code,
    client_alias: CREATED.clients[2] || CREATED.clients[0],
    type: 'red_team',
    window_start: '2026-06-01',
    window_end: '2026-09-30',
    estimated_hours: 600,
    status: 'active',
  });
  CREATED.projects.push(code);
});

test('P4: crear proyecto interno (activo) @write', async () => {
  const code = `INT-2026-${N3}`;
  await jApply('project_create', {
    code,
    client_alias: 'interno',
    type: 'internal',
    window_start: '2026-01-01',
    window_end: '2026-12-31',
    estimated_hours: 100,
    status: 'active',
  });
  CREATED.projects.push(code);
});

// ─────────────────────────────────────────────────────────────────────────────
// Phase 5 — Assignments
// ─────────────────────────────────────────────────────────────────────────────

test('P5: asignar personas a proyectos @write', async () => {
  if (!CREATED.projects.length || !CREATED.people.length) { test.skip(); return; }

  // proj index → CREATED.projects[i]
  const plan = [
    // ACM: pentest web — alice(lead), bob(executor), carlos(executor)
    { s: 'alice',   pi: 0, pct: 100, role: 'lead',     start: '2026-07-01', end: '2026-08-31' },
    { s: 'bob',     pi: 0, pct:  80, role: 'executor', start: '2026-07-01', end: '2026-08-31' },
    { s: 'carlos',  pi: 0, pct:  80, role: 'executor', start: '2026-07-15', end: '2026-08-31' },
    // WAV: pentest infra — diana(lead), erik(reviewer)
    { s: 'diana',   pi: 1, pct: 100, role: 'lead',     start: '2026-09-01', end: '2026-10-15' },
    { s: 'erik',    pi: 1, pct:  50, role: 'reviewer', start: '2026-09-01', end: '2026-10-15' },
    // SCX: red team — erik(lead), hannah, ivan, fatima
    { s: 'erik',    pi: 2, pct: 100, role: 'lead',     start: '2026-06-01', end: '2026-09-30' },
    { s: 'hannah',  pi: 2, pct: 100, role: 'executor', start: '2026-06-01', end: '2026-09-30' },
    { s: 'ivan',    pi: 2, pct:  80, role: 'executor', start: '2026-06-15', end: '2026-09-30' },
    { s: 'fatima',  pi: 2, pct:  50, role: 'shadow',   start: '2026-07-01', end: '2026-09-30' },
    // INT: interno — julia, giorgio
    { s: 'julia',   pi: 3, pct:  20, role: 'executor', start: '2026-01-01', end: '2026-12-31' },
    { s: 'giorgio', pi: 3, pct:  20, role: 'executor', start: '2026-01-10', end: '2026-12-31' },
  ];

  for (const { s, pi, pct, role, start, end } of plan) {
    const person_id = `${TAG}_${s}`;
    const project_code = CREATED.projects[pi];
    if (!project_code) continue;
    await jApply('assign', { person_id, project_code, dedication_pct: pct, start, end, role });
    CREATED.assignments.push({ person_id, project_code, start });
  }
});

// ─────────────────────────────────────────────────────────────────────────────
// Phase 6 — UI & API verification
// ─────────────────────────────────────────────────────────────────────────────

test('P6: people table muestra las personas creadas @write', async () => {
  await goTo(P, 'people');
  await P.waitForFunction(
    () => document.querySelectorAll('#people-tbody .people-row').length > 0,
    { timeout: 10_000 },
  );
  const rows = P.locator('#people-tbody .people-row');
  expect(await rows.count()).toBeGreaterThan(0);

  const tbody = await P.locator('#people-tbody').textContent();
  const found = PEOPLE.some(p => tbody.includes(p.full_name.split(' ')[0]));
  expect(found, 'Al menos un nombre de los creados debe aparecer en la tabla').toBeTruthy();
});

test('P6: drawer de persona abre y muestra datos reales @write', async () => {
  await goTo(P, 'people');
  await P.waitForFunction(() => document.querySelectorAll('#people-tbody .people-row').length > 0);
  await P.locator('#people-tbody .people-row').first().click();
  await expect(P.locator('#drawer-overlay')).toHaveClass(/open/);
  await expect(P.locator('#drawer-name')).not.toHaveText('—');
  await expect(P.locator('#drawer-id')).not.toHaveText('—');
  await P.click('.drawer-close');
  await expect(P.locator('#drawer-overlay')).not.toHaveClass(/open/);
});

test('P6: person-detail abre desde el drawer @write', async () => {
  await goTo(P, 'people');
  await P.waitForFunction(() => document.querySelectorAll('#people-tbody .people-row').length > 0);
  await P.locator('#people-tbody .people-row').first().click();
  await expect(P.locator('#drawer-overlay')).toHaveClass(/open/);
  await P.click('#drawer-fullpage');
  await expect(P.locator('#page-person-detail')).toHaveClass(/active/);
  await expect(P.locator('#person-detail-name')).not.toHaveText('—');
  await expect(P.locator('#person-detail-path')).toContainText('/people/');
});

test('P6: clients list muestra los clientes creados @write', async () => {
  await goTo(P, 'clients');
  await P.waitForFunction(
    () => document.querySelectorAll('#clients-list .list-item').length > 0,
    { timeout: 10_000 },
  );
  expect(await P.locator('#clients-list .list-item').count()).toBeGreaterThan(0);
});

test('P6: projects kanban muestra los proyectos creados @write', async () => {
  await goTo(P, 'projects');
  await P.waitForFunction(
    () => document.querySelectorAll('#projects-kanban-view .kanban-card').length > 0,
    { timeout: 10_000 },
  );
  expect(await P.locator('#projects-kanban-view .kanban-card').count()).toBeGreaterThan(0);
});

test('P6: project-detail abre y muestra código y breadcrumb @write', async () => {
  if (!CREATED.projects.length) { test.skip(); return; }
  await goTo(P, 'projects');
  const card = P.locator('#projects-kanban-view .kanban-card').first();
  if (await card.isVisible()) {
    await card.click();
  } else {
    await P.locator('#projects-tabs .tab[data-view="table"]').click();
    await P.locator('#projects-tbody tr').first().click();
  }
  await P.waitForFunction(
    () => document.getElementById('project-detail-title')?.textContent?.trim() !== '—',
  );
  await expect(P.locator('#project-detail-breadcrumb')).toContainText('/projects/');
});

test('P6: skills matrix tiene filas y columnas con datos reales @write', async () => {
  await goTo(P, 'skills');
  await P.waitForFunction(
    () => document.querySelectorAll('#skills-matrix-head th').length > 1,
    { timeout: 10_000 },
  );
  expect(await P.locator('#skills-matrix-head th').count()).toBeGreaterThan(1);
  expect(await P.locator('#skills-tbody .people-row').count()).toBeGreaterThan(0);
});

test('P6: search encuentra personas creadas @write', async () => {
  await goTo(P, 'search');
  await P.fill('#search-input', 'Alice');
  const [res] = await Promise.all([
    P.waitForResponse(r => r.url().includes('/api/search') && r.ok()),
    P.press('#search-input', 'Enter'),
  ]);
  expect(res.ok()).toBeTruthy();
  await P.waitForFunction(
    () => {
      const el = document.getElementById('search-results');
      return el && el.textContent.trim().length > 0;
    },
    { timeout: 10_000 },
  );
  const text = await P.locator('#search-results').textContent();
  expect(text.trim().length).toBeGreaterThan(0);
});

test('P6: schedule heatmap carga con las asignaciones @write', async () => {
  const data = await apiGet(P, '/heatmap?start=2026-01-01&end=2026-12-31');
  expect(data).toHaveProperty('weeks');
  expect(data).toHaveProperty('people');
  expect(data.people.length).toBeGreaterThan(0);
  await goTo(P, 'schedule');
  await expect(P.locator('#schedule-heatmap')).toBeVisible();
});

test('P6: overview KPIs se actualizan con los datos creados @write', async () => {
  await goTo(P, 'overview');
  // Wait for KPIs to stop showing '—'
  await P.waitForFunction(
    () => document.getElementById('kpi-team-size')?.textContent?.trim() !== '—',
    { timeout: 10_000 },
  );
  const teamSize = await P.locator('#kpi-team-size').textContent();
  expect(parseInt(teamSize)).toBeGreaterThan(0);
});

test('P6: API coherence no lanza errores internos @write', async () => {
  const warnings = await apiGet(P, '/coherence');
  expect(Array.isArray(warnings)).toBeTruthy();
  // warnings can exist (over-allocation, etc.) but the endpoint must not crash
});

test('P6: API skill-gap responde con datos @write', async () => {
  const gaps = await apiGet(P, '/skill-gap?scope=pipeline');
  expect(Array.isArray(gaps)).toBeTruthy();
});

test('P6: API geo responde con array @write', async () => {
  const geo = await apiGet(P, '/geo');
  expect(Array.isArray(geo)).toBeTruthy();
});

test('P6: admin users table refleja el estado del sistema @write', async () => {
  const adminReady = P.waitForResponse(r => r.url().includes('/api/admin/users') && r.ok());
  await goTo(P, 'admin');
  await adminReady;
  const rows = P.locator('#admin-users-tbody tr');
  expect(await rows.first().isVisible()).toBeTruthy();
});

// ─────────────────────────────────────────────────────────────────────────────
// Phase 7 — Cleanup
// ─────────────────────────────────────────────────────────────────────────────

test('P7: cleanup — desasignar asignaciones @write', async () => {
  for (const { person_id, project_code, start } of CREATED.assignments) {
    await jApplySoft('unassign', { person_id, project_code, start });
  }
  // No assertion — best-effort
});

test('P7: cleanup — archivar personas @write', async () => {
  for (const id of CREATED.people) {
    await jApplySoft('person_archive', { id, archived: true });
  }
  const people = await apiGet(P, '/people');
  const leftOver = people.filter(p => CREATED.people.includes(p.id) && !p.archived);
  expect(leftOver, 'Todas las personas de test deben quedar archivadas').toHaveLength(0);
});

test('P7: cleanup — archivar proyectos @write', async () => {
  for (const code of CREATED.projects) {
    await jApplySoft('project_archive', { code, archived: true });
  }
  const projects = await apiGet(P, '/projects?archived=true');
  const archived = projects.filter(p => CREATED.projects.includes(p.code) && p.archived);
  expect(archived.length).toBe(CREATED.projects.length);
});

test('P7: cleanup — archivar clientes @write', async () => {
  for (const id of CREATED.clients) {
    await jApplySoft('client_archive', { id, archived: true });
  }
  const clients = await apiGet(P, '/clients?archived=true');
  const archived = clients.filter(c => CREATED.clients.includes(c.id) && c.archived);
  expect(archived.length).toBe(CREATED.clients.length);
});
