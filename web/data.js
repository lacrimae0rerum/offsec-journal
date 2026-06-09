// ===================== EMPTY SHELL =====================
// All seed data removed (Apr 27 2026). The DATA object only keeps the SHAPE
// expected by app.js so render functions don't crash on first paint.
// Real data is fetched from the FastAPI backend by api.js / app.js
// (GET /api/people, /api/clients, /api/projects, ...).

const DATA = {
  people: [],
  projects: [],
  clients: [],
  skills: [],
  skillGaps: [],
  coherenceWarnings: [],
  recentJournal: [],
  journal: [],

  // Skills matrix — kept empty; columns are sourced from /api/skills now.
  skillsMatrix: { cols: [], rows: {} },

  // Schedule heatmap (people × weeks). Filled from /api/heatmap.
  // scheduleWeeks is the column header (one entry per displayed week);
  // app.js reads .length when falling back from API to derive a stable size.
  scheduleWeeks: [],
  schedule: {},
  scheduleBreakdowns: {},
  overviewPatterns: {},
};

