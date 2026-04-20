# web/ — Frontend estático

Prototipo HTML/CSS/JS de 12 páginas implementando el wireframe original. Actúa como spec visual y como UI navegable mientras el frontend Next.js no exista.

Estado actual: lee datos hardcoded de `data.js`. Siguiente paso (Prioridad 1 en [../PLAN.md](../PLAN.md)): sustituir `DATA.*` por `fetch('/api/...')` con header `X-API-Key`.

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

Todos envían `POST /api/journal` con el kind tipado cuando el backend está online (badge top-right verde). Si no, el modal avisa de configurar la API key en el panel Tweaks.

Tweaks panel (gear icon abajo-derecha): API Base URL, API Key (persistencia localStorage), sidebar full/mini, schedule hover/click.

## Archivos

```
index.html    structure de 12 páginas + 9 modales + drawer + status badge
styles.css    design tokens azul accent (black + #1e9be0) + componentes + conn-status
app.js        nav, radar SVG, 2 heatmaps, drawer, 9 modales handlers, api probe, tweaks
api.js        wrapper fetch con X-API-Key + 20 métodos tipados
data.js       seed: 6 personas, 8 proyectos, 3 clientes, journal, skills matrix
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

**Config runtime — un solo comando**

1. `make install` en raíz — genera `.env` con `API_KEY` aleatoria
2. `make up` — arranca FastAPI en :8000 sirviendo también el frontend
3. Abrir http://localhost:8000/ → el badge se pone verde automáticamente (auto-bootstrap desde `/api/bootstrap`, solo accesible desde loopback)

Para despliegues remotos (no loopback), pega la key manualmente en el panel ⚙.

**Migración pendiente** — ver Prioridad 1 en [../PLAN.md](../PLAN.md).

No se toca Next.js hasta que el estático no baste (P5 del PLAN).
