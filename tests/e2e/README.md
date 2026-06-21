# E2E Tests — OffSec Journal (Playwright)

Suite de tests end-to-end que ejercita el frontend en el navegador real,
complementando los 200 tests de integración FastAPI (`tests/`).

## Pre-requisitos

- Docker dev server corriendo: `docker compose up -d`  
  (lanza la app en `127.0.0.1:8001` con `DEV_USER=fer` — sin Authelia)
- Node.js ≥ 18

## Instalación

```bash
cd tests/e2e
npm install
npx playwright install chromium
```

## Ejecutar

```bash
# Suite completa
npm test

# Con navegador visible
npm run test:headed

# UI interactiva (Playwright Test UI)
npm run test:ui

# Solo smoke tests (rápido, sin mutaciones)
npm run test:smoke

# Solo journal (CRUD cycle)
npm run test:journal

# Contra servidor alternativo
BASE_URL=http://127.0.0.1:8000 npm test
```

## Estructura

| Archivo | Cubre |
|---|---|
| `00-smoke.spec.js` | API health, auth, endpoints básicos |
| `01-overview.spec.js` | Página de inicio, KPIs, heatmap, journal reciente |
| `02-people.spec.js` | Lista, drawer, person-detail, modales persona/PTO |
| `03-projects.spec.js` | Lista, kanban/tabla, project-detail, modal nuevo proyecto |
| `04-clients.spec.js` | Lista, detalle de cliente, modal nuevo cliente |
| `05-journal.spec.js` | Tabs pending/applied/rejected, crear entry, aplicar, rechazar |
| `06-search.spec.js` | Query, filtros por tipo, fechas, limpiar |
| `07-admin.spec.js` | Users table, auth-events, crear/archivar usuario |
| `08-skills.spec.js` | Matriz, catálogo, gaps, modal nueva skill |
| `09-schedule-map-chat.spec.js` | Heatmap de schedule, mapa geo, página chat (mock) |
| `10-notes.spec.js` | Notas vía API, sección notas en person/project-detail |

## Notas de diseño

- **Sin contaminación de datos**: los tests de escritura crean entries de tipo
  `skill_update` con nivel existente (cambio neutro) y las rechazan al finalizar.
- **Resiliencia**: los asserts comprueban que los elementos existen y tienen contenido,
  no valores exactos (la base de datos del dev puede variar).
- **Dependencia de datos mínima**: solo asume que el usuario `fer` existe
  (es la única persona en `data/offsec/people.yaml` post-limpieza N0.1) y que
  hay al menos 1 skill en catálogo.
- **Autenticación**: `DEV_USER=fer` en `docker-compose.yml` actúa como bypass
  global — ningún test necesita cookies ni headers de Authelia.
