// ===================== SEED DATA =====================
// Matches the YAML source-of-truth described in OffSec Journal Prompt.md.
// When the real backend lands, this file is replaced by fetch() calls to
// the FastAPI endpoints (GET /api/people, /api/projects, ...).

const DATA = {
  people: [
    {
      id: 'fer', name: 'Alex P.', office: 'Madrid', city: 'Madrid',
      tz: 'CET', level: 'senior', fte: 1.0, start: '2019-03-01',
      langs: ['es', 'en'], load: 80, warning: null,
      skills: [
        { id: 'hacking_web', lvl: 3, last: 'PT-2026-012', growth: false },
        { id: 'hacking_ad', lvl: 4, last: 'PT-2026-012', growth: false },
        { id: 'osint', lvl: 4, last: 'CTI-2026-003', growth: false },
        { id: 'escalada_privilegios', lvl: 2, last: null, growth: false },
        { id: 'reporting', lvl: 4, last: 'PT-2026-012', growth: false },
        { id: 'hacking_cloud', lvl: 2, last: null, growth: true },
        { id: 'automatizacion_tooling', lvl: 3, last: 'CTI-2026-003', growth: false },
      ],
      assignments: [
        { project: 'PT-2026-012', role: 'lead', pct: 50, window: 'Abr 7 → Abr 25' },
        { project: 'CTI-2026-003', role: 'executor', pct: 30, window: 'Ene → Dic' },
      ],
      coherence: { ok: true, msg: '✓ senior coherente — 2 skills L4, top-5 avg 3.6' },
      availability: [
        { kind: 'pto', window: '2026-04-21 → 2026-04-25', pct: 100, reason: 'Vacaciones', status: 'applied' },
        { kind: 'training', window: '2026-05-11 → 2026-05-15', pct: 50, reason: 'HTB Cloud course', status: 'applied' },
      ],
      notes: [
        { date: '2026-04-15', author: 'fer', tags: ['mentoring', 'osint'], body: 'Mentoring tbd_04 en OSINT básico. Buena evolución primera semana. Sugerir pareja con santi para AD en mayo.' },
        { date: '2026-04-02', author: 'fer', tags: ['cti', 'client-delta'], body: 'Retainer Cliente Delta renovado Q2. Aumentar dedicación si entra phishing campaign nueva.' },
        { date: '2026-03-20', author: 'santi', tags: ['pto'], body: 'Fer avisa PTO 21-25 abr. Confirmado via journal.' },
      ]
    },
    {
      id: 'santi', name: 'Sam R.', office: 'Madrid', city: 'Madrid',
      tz: 'CET', level: 'senior', fte: 1.0, start: '2020-09-01',
      langs: ['es', 'en'], load: 100, warning: null,
      skills: [
        { id: 'hacking_web', lvl: 4, last: 'PT-2026-014', growth: false },
        { id: 'hacking_ad', lvl: 4, last: 'PT-2026-014', growth: false },
        { id: 'escalada_privilegios', lvl: 4, last: 'RT-2026-003', growth: false },
        { id: 'bypass_autenticacion', lvl: 3, last: 'PT-2026-014', growth: false },
        { id: 'reporting', lvl: 3, last: 'RT-2026-003', growth: false },
      ],
      assignments: [
        { project: 'PT-2026-014', role: 'lead', pct: 50, window: 'Abr 14 → May 9' },
        { project: 'RT-2026-003', role: 'executor', pct: 50, window: 'Mar 1 → Abr 30' },
      ],
      coherence: { ok: true, msg: '✓ senior coherente' },
      availability: [],
      notes: []
    },
    {
      id: 'tbd_01', name: 'Operador 01', office: 'Barcelona', city: 'Barcelona',
      tz: 'CET', level: 'intermediate', fte: 1.0, start: '2024-06-15',
      langs: ['es'], load: 60, warning: null,
      skills: [
        { id: 'hacking_web', lvl: 3, last: 'PT-2026-012', growth: false },
        { id: 'osint', lvl: 2, last: null, growth: true },
        { id: 'reporting', lvl: 2, last: 'PT-2026-012', growth: false },
      ],
      assignments: [
        { project: 'PT-2026-012', role: 'executor', pct: 40, window: 'Abr 7 → Abr 25' },
      ],
      coherence: { ok: true, msg: '✓ intermediate coherente' },
      availability: [],
      notes: []
    },
    {
      id: 'tbd_02', name: 'Operador 02', office: 'Barcelona', city: 'Barcelona',
      tz: 'CET', level: 'intermediate', fte: 1.0, start: '2025-01-10',
      langs: ['es'], load: 50, warning: null,
      skills: [
        { id: 'hacking_ad', lvl: 3, last: 'RT-2026-003', growth: false },
        { id: 'pivoting_movimiento_lateral', lvl: 3, last: 'RT-2026-003', growth: false },
        { id: 'hacking_cloud', lvl: 0, last: null, growth: true },
      ],
      assignments: [
        { project: 'RT-2026-003', role: 'executor', pct: 30, window: 'Mar 1 → Abr 30' },
      ],
      coherence: { ok: true, msg: '✓ intermediate coherente' },
      availability: [],
      notes: []
    },
    {
      id: 'tbd_03', name: 'Operador 03', office: 'Remote', city: 'Remote',
      tz: 'CET', level: 'senior', fte: 1.0, start: '2025-10-01',
      langs: ['es', 'en'], load: 70, warning: 'insufficient_skill_coverage',
      skills: [
        { id: 'hacking_web', lvl: 2, last: 'PT-2026-014', growth: false },
        { id: 'osint', lvl: 1, last: null, growth: false },
        { id: 'escalada_privilegios', lvl: 2, last: null, growth: false },
        { id: 'reporting', lvl: 2, last: null, growth: false },
      ],
      assignments: [
        { project: 'PT-2026-014', role: 'executor', pct: 40, window: 'Abr 14 → May 9' },
        { project: 'CTI-2026-003', role: 'reviewer', pct: 30, window: 'Ene → Dic' },
      ],
      coherence: {
        ok: false,
        msg: 'insufficient_skill_coverage',
        detail: 'Marcado senior pero sólo 4 PersonSkill con level≥1 (regla pide ≥5).'
      },
      availability: [],
      notes: []
    },
    {
      id: 'tbd_04', name: 'Operador 04', office: 'Lisboa', city: 'Lisboa',
      tz: 'WET', level: 'junior', fte: 1.0, start: '2026-03-01',
      langs: ['pt', 'en'], load: 30, warning: null,
      skills: [
        { id: 'osint', lvl: 1, last: null, growth: true },
        { id: 'reporting', lvl: 1, last: null, growth: false },
      ],
      assignments: [
        { project: 'PT-2026-012', role: 'shadow', pct: 20, window: 'Abr 7 → Abr 25' },
      ],
      coherence: { ok: true, msg: '✓ junior coherente' },
      availability: [],
      notes: []
    },
  ],

  projects: [
    { code: 'PT-2026-018', type: 'pentest_web', client: 'Cliente Alfa', window: 'May 12 → Jun 6', status: 'pipeline', coverage: 40, assigned: 0, total: 2 },
    { code: 'RT-2026-005', type: 'red_team', client: 'Cliente Beta', window: 'Jun 1 → Jul 15', status: 'pipeline', coverage: 60, assigned: 1, total: 3 },
    { code: 'RES-2026-001', type: 'research', client: 'Interno', window: 'Jun → ongoing', status: 'pipeline', coverage: null, assigned: 0, total: 1 },
    { code: 'PT-2026-012', type: 'pentest_web', client: 'Cliente Gamma', window: 'Abr 7 → Abr 25', status: 'active', coverage: 100, assigned: 3, total: 3 },
    { code: 'PT-2026-014', type: 'pentest_web', client: 'Cliente Delta', window: 'Abr 14 → May 9', status: 'active', coverage: 85, assigned: 2, total: 3 },
    { code: 'RT-2026-003', type: 'red_team', client: 'Cliente Epsilon', window: 'Mar 1 → Abr 30', status: 'active', coverage: 90, assigned: 3, total: 3 },
    { code: 'CTI-2026-003', type: 'cti_retainer', client: 'Cliente Zeta', window: 'Ene → Dic', status: 'active', coverage: 100, assigned: 2, total: 2 },
    { code: 'PUR-2026-001', type: 'purple', client: 'Cliente Eta', window: 'Abr 1 → Abr 30', status: 'active', coverage: 70, assigned: 2, total: 3 },
  ],

  clients: [
    {
      id: 'alfa', name: 'Cliente Alfa', sector: 'Banca', size: 'Enterprise', country: 'ES', status: 'activo',
      description: 'Gran banco español con infraestructura híbrida AWS/on-prem. Foco en compliance PCI-DSS y tests anuales de red team. Relación desde 2023.',
      projects: [
        { code: 'PT-2026-018', type: 'pentest_web', window: 'May 12 → Jun 6', status: 'pipeline', coverage: 40 },
        { code: 'RT-2025-011', type: 'red_team', window: 'Oct 2025', status: 'closed', coverage: 100 },
      ],
      contacts: [
        { initials: 'CV', name: 'Carlos Vega', role: 'CISO', email: 'carlos.vega@alfa.example' },
        { initials: 'MS', name: 'Marta Soler', role: 'IT Manager', email: 'marta.soler@alfa.example' },
      ],
      notes: [
        { date: '2026-03-10', author: 'fer', body: 'Kickoff RT-2025-011 bien recibido. Piden test cloud AWS para Q2 2026.' }
      ]
    },
    {
      id: 'gamma', name: 'Cliente Gamma', sector: 'Retail', size: 'Mid-market', country: 'ES', status: 'activo',
      description: 'Retailer con presencia europea. Test anual de aplicación e-commerce.',
      projects: [
        { code: 'PT-2026-012', type: 'pentest_web', window: 'Abr 7 → Abr 25', status: 'active', coverage: 100 },
      ],
      contacts: [],
      notes: []
    },
    {
      id: 'epsilon', name: 'Cliente Epsilon', sector: 'Energía', size: 'Enterprise', country: 'PT', status: 'activo',
      description: 'Operador energético portugués. Red team anual.',
      projects: [
        { code: 'RT-2026-003', type: 'red_team', window: 'Mar 1 → Abr 30', status: 'active', coverage: 90 },
      ],
      contacts: [],
      notes: []
    },
  ],

  skillGaps: [
    { skill: 'hacking_cloud', need: 3, have: 1, deficit: 2, severity: 'rose' },
    { skill: 'escalada_privilegios', need: 4, have: 3, deficit: 1, severity: 'rose' },
    { skill: 'evasion_defensas', need: 2, have: 0, deficit: 2, severity: 'amber' },
    { skill: 'hacking_contenedores', need: 2, have: 0, deficit: 2, severity: 'amber' },
  ],

  coherenceWarnings: [
    {
      person: 'tbd_03',
      rule: 'insufficient_skill_coverage',
      detail: 'Marcado senior pero sólo 4 PersonSkill con level≥1 (regla pide ≥5). Revisar global_level o completar skills.',
      severity: 'warning'
    },
    {
      person: 'tbd_04',
      rule: 'junior_with_high_skills',
      detail: 'Marcado junior pero tiene 0 skills con L≥4 (sin warning; regla no dispara). Revisar si hay que subir a intermediate en 3 meses.',
      severity: 'warning'
    }
  ],

  recentJournal: [
    { status: 'applied', kind: 'assign', text: 'santi → PT-2026-014, 50%, lead', ago: 'hace 2h' },
    { status: 'pending', kind: 'skill_update', text: 'tbd_01: hacking_web L3 → L4', ago: 'hace 5h' },
    { status: 'applied', kind: 'availability', text: 'fer: PTO 21–25 abr', ago: 'hace 1d' },
  ],

  journal: [
    {
      id: '01HYXZABC', ts: 'hace 5h', ago: 'hace 5h',
      status: 'pending', proposer: 'llm', kind: 'skill_update',
      title: 'Subir tbd_01.hacking_web de L3 → L4',
      body: 'Propuesto por el asistente tras revisar desempeño en PT-2026-012.'
    },
    {
      id: '01HYXWXYZ', ts: 'hace 2h', ago: 'hace 2h',
      status: 'applied', proposer: 'llm', kind: 'assign',
      title: 'santi → PT-2026-014, 50%, lead',
      body: 'applied 14:32'
    },
    {
      id: '01HYXUDEF', ts: 'hace 1d', ago: 'hace 1d',
      status: 'applied', proposer: 'human', kind: 'availability',
      title: 'fer: PTO 21–25 abr, 100%',
      body: 'applied ayer'
    },
  ],

  // Skills matrix (10 columns — matches ui header)
  skillsMatrix: {
    cols: ['web', 'ad', 'osint', 'priv', 'pivot', 'cloud', 'report', 'auto', 'phish', 'evas'],
    rows: {
      fer:    [3, 4, 4, 2, 2, 2, 4, 3, 1, 1],
      santi:  [4, 4, 2, 4, 4, 1, 3, 2, 2, 2],
      tbd_01: [3, 2, 2, 2, 1, 0, 2, 1, 0, 0],
      tbd_02: [2, 3, 1, 2, 3, 0, 2, 1, 1, 2],
      tbd_03: [2, 2, 1, 2, 1, 0, 2, 1, 0, 0],
      tbd_04: [1, 0, 1, 0, 0, 0, 1, 0, 0, 0],
    }
  },

  // Schedule heatmap (6 people × 4 weeks W15-W18)
  scheduleWeeks: ['W15', 'W16', 'W17', 'W18'],
  schedule: {
    fer:    [80, 80, 80, 0],
    santi:  [100, 100, 100, 50],
    tbd_01: [60, 60, 60, 60],
    tbd_02: [50, 110, 50, 50],
    tbd_03: [70, 70, 70, 70],
    tbd_04: [30, 30, 30, 30],
  },
  scheduleBreakdowns: {
    fer:    [{ code: 'PT-2026-012', pct: 50, role: 'lead', h: 20 }, { code: 'CTI-2026-003', pct: 30, role: 'executor', h: 12 }],
    santi:  [{ code: 'PT-2026-014', pct: 50, role: 'lead', h: 20 }, { code: 'RT-2026-003', pct: 50, role: 'executor', h: 20 }],
    tbd_01: [{ code: 'PT-2026-012', pct: 40, role: 'executor', h: 16 }, { code: 'PUR-2026-001', pct: 20, role: 'shadow', h: 8 }],
    tbd_02: [{ code: 'RT-2026-003', pct: 30, role: 'executor', h: 12 }, { code: 'PUR-2026-001', pct: 20, role: 'executor', h: 8 }],
    tbd_03: [{ code: 'PT-2026-014', pct: 40, role: 'executor', h: 16 }, { code: 'CTI-2026-003', pct: 30, role: 'reviewer', h: 12 }],
    tbd_04: [{ code: 'PT-2026-012', pct: 20, role: 'shadow', h: 8 }, { code: 'training', pct: 10, role: '—', h: 4 }],
  },

  // Overview heatmap patterns (26 weeks to cycle through)
  overviewPatterns: {
    fer:    [80, 80, 0, 0, 0, 80, 70, 70, 80, 80, 0, 0, 60, 80, 80, 70, 80, 80, 0, 0, 80, 60, 70, 80, 0, 0],
    santi:  [50, 100, 100, 100, 100, 50, 100, 100, 80, 50, 100, 100, 100, 50, 80, 80, 100, 100, 50, 100, 80, 100, 50, 100, 100, 50],
    tbd_01: [60, 60, 60, 0, 0, 60, 60, 0, 60, 60, 60, 0, 0, 60, 60, 60, 0, 60, 60, 60, 0, 60, 60, 0, 0, 60],
    tbd_02: [50, 110, 50, 50, 0, 50, 50, 50, 0, 50, 110, 50, 50, 0, 50, 50, 50, 50, 0, 50, 50, 110, 50, 0, 50, 50],
    tbd_03: [70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70],
    tbd_04: [30, 30, 0, 0, 0, 30, 0, 30, 0, 30, 30, 0, 0, 30, 30, 0, 0, 30, 30, 0, 30, 0, 30, 30, 0, 0],
  }
};

// Radar chart axes (shared by drawer + person detail)
const RADAR_AXES = ['web', 'ad', 'osint', 'priv', 'report', 'cloud'];

// For building hexagon vertices at level L (0..5) on a 200×200 viewBox
// centered at (100,100) with max radius 80. Axes start at top going clockwise.
function radarPoints(levels /* length 6, 0..5 */, radius = 80) {
  const cx = 100, cy = 100;
  return levels.map((lvl, i) => {
    const angle = -Math.PI / 2 + (i * 2 * Math.PI) / 6;
    const r = (lvl / 5) * radius;
    return [cx + r * Math.cos(angle), cy + r * Math.sin(angle)];
  });
}
