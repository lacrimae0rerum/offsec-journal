# web/ — Frontend estático

Prototipo HTML/CSS/JS de 12 páginas implementando el wireframe original. Actúa como spec visual y como UI navegable mientras el frontend Next.js no exista.

Auth: la página se sirve desde el mismo dominio que el backend, detrás de nginx + Authelia. Todo `fetch()` va al mismo origen con `credentials: 'include'` — el navegador carga la cookie `authelia_session` y nginx inyecta `Remote-User` al backend. Sin cookie, nginx redirige al login de Authelia antes de que el JS siquiera se evalúe. Si el user está autenticado pero no registrado en la tabla `user` de la app, `bootstrapApp()` pinta el overlay `#no-access-overlay` con un link al logout de Authelia.

## Páginas

| Página | Estado | Ruta |
|---|---|---|
| Overview | ✅ completa — KPIs + heatmap 1S–6M (altura celdas uniforme, 7 tramos de color) + gaps + coherence + journal | `#page-overview` |
| People | ✅ tabla + filtros + drawer con skill radar | `#page-people` |
| Person detail | ✅ radar 6-ejes, skills, assignments, coherence, availability, notas paginadas | `#page-person-detail` |
| Projects | ✅ kanban ↔ tabla toggle + `+ Nuevo proyecto` modal | `#page-projects` |
| Project detail | ✅ required skills vs equipo + timeline + notas | `#page-project-detail` |
| Clients | ✅ master-list + detalle con proyectos/contactos/notas | `#page-clients` |
| Schedule | ✅ heatmap persona × semana con popover (hover/click tweak), over-allocation en rojo | `#page-schedule` |
| Skills | ✅ matriz de niveles ↔ gap bars toggle | `#page-skills` |
| Map | ✅ grid map con 3 markers + popover de personas | `#page-map` |
| Journal | ✅ pending/applied/rejected tabs, apply/reject, modal con reason | `#page-journal` |
| Chat | ✅ split con 3 flows mockeados + tool calls panel + streaming cursor | `#page-chat` |
| Search | ✅ facets + grouped results con highlight | `#page-search` |

Modales (15):

| Modal | Journal kind | Dispara desde |
|---|---|---|
| `reject-modal` | (reject con reason) | Journal pending → ✗ Rechazar |
| `new-project-modal` | `project_create` | Projects header + `+ Nuevo proyecto` |
| `new-person-modal` | `person_create` | People header + `+ Nueva persona` |
| `new-client-modal` | `client_create` | Clients header + sidebar `+ Nuevo cliente` |
| `new-avail-modal` | `availability` | Person detail + `+ PTO / training` |
| `new-catalog-skill-modal` | `skill_catalog_create` | Skills header + `+ Nueva skill` |
| `propose-assign-modal` | `assign` | Project detail + `+ Proponer assignment` |
| `archive-modal` | `*_archive` | Botones "Archivar" en Person / Project / Client |
| `contact-modal` | `contact_add/update/remove` | Client detail — add, click en row edita, eliminar desde modal |
| `skill-modal` | `skill_update` | Person detail — click en skill row edita, `+ Añadir skill` añade |
| **`edit-person-modal`** | `person_update` | Person detail header → `Editar persona` (diff automático) |
| **`edit-project-modal`** | `project_update` | Project detail header → `Editar proyecto` (diff automático) |
| **`edit-client-modal`** | `client_update` | Client detail header → `Editar` (diff automático) |
| **`edit-skill-label-modal`** | `skill_label_update` | Skills matrix header → icono ✎ junto a cada skill |
| **`req-skills-modal`** | `project_update` (required_skills) | Dentro de `edit-project-modal` → `Editar required skills →` |

Cada modal de edit tomas snapshot del original y hace **diff payload automático**: solo los campos modificados van en el POST, minimizando el riesgo de sobreescribir cambios concurrentes.

Todos envían `POST /api/journal` — el backend inyecta `ctx.team_slug` automáticamente desde `Remote-User`, así que la UI no pasa team ni user: el backend autoriza.

Identidad en la sidebar:
- `#team-badge` — pintado con color por team (OFFSEC rojo, INFOSEC azul) leyendo `me.team.slug`.
- `#sidebar-user-name` + `#sidebar-user-role` — display name + "admin"/"miembro".
- `#logout-link` — redirige a `me.logout_url` si el backend lo proporciona. Por defecto está vacío (el journal no gestiona la sesión), y entonces el enlace se oculta. Configurable por env `AUTHELIA_LOGOUT_URL`.

## Archivos

```
index.html    structure de 12 páginas + 16 modales + drawer + sidebar identity block + no-access overlay
styles.css    design tokens azul accent (black + #1e9be0) + team-badge + sidebar-footer + no-access-overlay
app.js        nav, radar SVG, 2 heatmaps, drawer, 16 modales handlers, bootstrapApp (/api/auth/me), paintIdentity
api.js        fetch wrapper con credentials:'include' + callbacks onUnauthenticated/onForbidden + 30+ métodos tipados
data.js       seed offline (sin uso en prod — util en dev cuando no hay backend)
README.md     este archivo
```

## Diseño

- Paleta: negro `#000` + azul accent `#1e9be0`
- Tipografía: Ubuntu UI / JetBrains Mono para IDs y códigos
- Estética sketch: dashed borders en cards — intencional per chat original
- Heatmap colors en `app.js:hmColor()` — 7 tramos:
  - 0% → transparent
  - 1-20% → azul 0.20
  - 21-40% → azul 0.38
  - 41-60% → azul 0.58
  - 61-80% → azul 0.80
  - 81-100% → ámbar 0.62 (near capacity)
  - >100% → rojo 0.78 (over-allocated)
- Overview heatmap: altura de celda uniforme para todos los rangos (1S → 6M) — se calcula a partir del ancho "2M-equivalente" en `buildOverviewHeatmap`

## Run

Servir `web/` estático (cualquier servidor HTTP vale):

```bash
# desde la raíz del repo
make web                     # python -m http.server 3000 en web/
# o
cd web && python -m http.server 3000
```

Abrir http://localhost:3000/. Los fetch tirarán de `data.js` hasta que se conecte el backend.

## Wire-up al backend

**Estado actual** — wire-up completo:

- ✅ `web/api.js` construido con wrapper, persistencia en localStorage, **4 normalizers** (person/project/client/journal)
- ✅ Settings UI (API Base URL + API Key) en el panel Tweaks
- ✅ Badge de estado online/offline/error arriba a la derecha
- ✅ **`refreshAll()`** — Promise.all a 8 endpoints, normaliza shapes, muta `DATA.*` en sitio y dispara `renderAll()`
- ✅ **`renderAll()`** — re-renderiza overview + people + projects + clients + skills + schedule + map tras cualquier mutación
- ✅ Journal page: list + apply + reject live
- ✅ 15 modales llaman `api.createJournal(kind, payload)` y disparan refresh automático al aplicar
- ✅ Overview: heatmap del backend (`/api/heatmap`), coherence warnings, skill gaps, últimos del journal
- ✅ People: load agregado desde assignments de todos los proyectos; warning sincronizado con coherence
- ✅ Projects + Client Detail: coverage calculado cliente-side (% de required skills cubiertos)
- ✅ Skills matrix: columnas **dinámicas** del catálogo del backend (crece si creas skills nuevas)
- ✅ Map: 3 markers actualizados con personas reales de cada oficina
- ✅ Search: input live con debounce 220ms + highlight de matches

Fallback: si una llamada a la API falla, esa rebanada queda en seed; el resto sigue funcionando.

**Config runtime — dev local**

1. `make install` en raíz — `.env` sin secrets (auth delegada a nginx+Authelia en prod)
2. `make up` — FastAPI en `127.0.0.1:8000` sirviendo también el frontend
3. Registrar tu usuario: `.venv/bin/offsec users add --username <u> --team offsec --role admin`
4. Para ejercitar el frontend en dev sin Authelia, usar curl/TestClient con `Remote-User: <u>` (el middleware exige proxy IP 127.0.0.1 + username en tabla).

En producción el `bootstrapApp()` de `app.js` pinta la sidebar tras llamar a `/api/auth/me`.

No se toca Next.js hasta que el estático no baste (P5 del PLAN).
