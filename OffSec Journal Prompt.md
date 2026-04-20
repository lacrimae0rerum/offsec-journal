<prompt>
<contexto>
Soy analista en un MSSP. Lidero parte del equipo de seguridad ofensiva (pentesting + CTI, pequeño, con colaborador directo). Necesito una **website interna de gestión de equipo** que corra en red local del MSSP, accesible para mí y mi colaborador desde nuestras máquinas.
El producto es una webapp fullstack diseñada y construida de principio a fin por Claude Code. No se apoya en herramientas externas de dashboarding. Todo — backend, frontend, datos, LLM conversacional, despliegue — vive en este repo.
Qué tiene que hacer la website:

Visualizar y gestionar personas del equipo, sus skills individuales y nivel global.
Visualizar y gestionar disponibilidad, dedicación por proyecto, nº proyectos, nivel de implicación.
Visualizar ubicación geográfica por oficina/ciudad.
Visualizar pipeline de proyectos vs capacidad del equipo (skill gap, carga).
Capa conversacional contra LLM local para consultas rápidas y propuestas de cambios.
Tomar notas sobre personas y proyectos.

Filosofía de producto — botón gordo: mínimo de comandos, defaults agresivos, idempotencia total. make install && make up y la website está viva. Si una acción recurrente requiere más de 2 pasos, el diseño falla.
Stack fijo (cerrado, no negociable):

Builder: Claude Code terminal, sin límite por turno.
Backend: FastAPI + Python 3.11+, SQLite (stdlib, FTS5 incluido), ruamel.yaml (round-trip preservando orden y comentarios).
Frontend: Next.js 14 (App Router) + TypeScript + Tailwind + shadcn/ui + Recharts + MapLibre GL + TanStack Query + Zod.
LLM: Llama 3.1 8B local vía Ollama nativo en el host (no en Docker; más rápido y menos fricción). El backend habla con Ollama; la webapp habla solo con el backend.
Orquestación: Docker Compose con dos servicios, api y web. Ollama corre nativo.
Despliegue: red local del MSSP. Acceso por http://<host-ip>:3000 desde las máquinas de los dos usuarios. Localhost en desarrollo.

Fuente de verdad: YAML en data/ versionado en git. SQLite es read-cache reconstruible con sync. Nunca al revés.
Write-path — patrón journal (cerrado): la LLM no muta entidades estructurales. Registra propuestas en data/journal.yaml con status=pending. El humano aplica o rechaza desde CLI o desde la página /journal de la webapp. journal apply crea .bak del YAML afectado, muta con ruamel, dispara sync. Si ruamel falla, restaura el .bak y reporta. Las notas son escritura directa (append-only a markdown).
Automatización last_used_on_project (cerrado): cuando journal apply aplica un assign de persona P a proyecto X, para cada skill en X.required_skills que P tenga con level ≥ 1, se actualiza PersonSkill.last_used_on_project = X.code. En core/queries.apply_journal_entry(), con test.
Rúbrica skills (fijada):

Individuales 1–5: 1 teoría, 2 shadow supervisado, 3 ejecutor autónomo, 4 lead técnico, 5 referente/formador.
Global operador: junior | intermediate | senior | master, manual.

Check coherencia global_level ↔ skills (cerrado, warnings no bloqueantes):

master: ≥3 skills nivel ≥4.
senior: ≥2 skills nivel ≥4 Y promedio top-5 (con level≥1) ≥3.5.
intermediate: ≥3 skills nivel ≥3.
junior: warn si ≥2 skills nivel ≥4.
Si <5 PersonSkill con level≥1, senior/master emiten "insufficient_skill_coverage" en lugar del check numérico.

Warnings en validate, en GET /api/people/{id}/coherence y consolidados en GET /api/coherence.
Catálogo cerrado de 20 skills (ids snake_case, label_es literal):
reconocimiento_externo, osint, hacking_web, bypass_autenticacion,
explotacion_logica_negocio, hacking_active_directory,
pivoting_movimiento_lateral, escalada_privilegios,
explotacion_servicios_red, phishing, ingenieria_social,
desarrollo_ofensivo, evasion_defensas, desarrollo_exploits,
hacking_cloud, hacking_contenedores, acceso_fisico,
evasion_controles_red, reporting, automatizacion_tooling
Cada skill description: "TODO: operator-defined". Fer las escribe después. OPEN_QUESTIONS lo marca como bloqueante suave para señal de min_level.
Decisiones de producto defaulteadas por mí, no te las preguntes:

Streaming de tokens en /chat: obligatorio V1. SSE desde Ollama, propagado por el backend al frontend. Sin streaming, 20s de silencio por turno mata la sensación de uso.
Conflicto de puertos en make up: detección automática. Si 3000 u 8000 están ocupados, sube 3001/8001, imprime banner claro con las URLs finales y persiste la elección en .env.local. No fallar ruidoso.
Número de páginas: 9 como listadas abajo, diseño coherente entre ellas vía sistema de componentes compartidos. Nada de colapsar.
Theming: dark-only V1. Sin toggle.
Autenticación: header X-API-Key en backend, autogenerado en make install, leído por el proxy Next server-side. La webapp no pide login (red local del MSSP, 2 usuarios). V2 si se expone fuera.
shadcn/ui: instalados inlined en web/components/ui/ directamente como ficheros TSX escritos por Claude, no vía npx shadcn add. Elimina la fricción del CLI interactivo en make install. Usa los patterns de shadcn pero no dependas del CLI.
MapLibre: tiles OSM raster públicos, sin token. Adecuado para red local + volumen bajo.
Tests: 5 Python (pytest) + 1 suite frontend (Vitest) con casos concretos especificados abajo. No son decoración.
</contexto>


<tarea>
Diseña y construye un repo fullstack ejecutable con los siguientes componentes. Orden de implementación sugerido: backend con `doctor` en verde → seed → tests Python → frontend layout y sistema de diseño → 9 páginas → streaming chat → polish.
1. Modelo de datos (YAML source-of-truth + SQLite read-cache, ruamel.yaml con typ='rt')
Entidades:

Person: id (snake_case alias), full_name, office, city, timezone, languages (list), base_role, global_level (junior|intermediate|senior|master), contractual_fte (float 0–1), start_date. Campo embebido skills: list de {skill_id, level (1-5), last_used_on_project (code|null), growth_interest (bool)}.
Skill: id, label_es, description. Catálogo fijo, sin jerarquía.
Project: code, client_alias, type (pentest_web|red_team|purple|cti_retainer|research|internal), window_start, window_end, required_skills (list {skill_id, weight 1–3, min_level 1–5}), estimated_hours (int), status (pipeline|active|closed).
Assignment: person_id, project_code, dedication_pct (0–100), start, end, role (lead|executor|reviewer|shadow).
Availability: person_id, kind (pto|sick|training|overhead|hold), start, end, pct (default 100).
Note: fichero markdown append-only en notes/persons/<id>.md o notes/projects/<code>.md. Separador --- timestamp | author | tags ---. FTS5 indexa.
Office: office_id, city, country, lat, lon (en data/offices.yaml).
JournalEntry (data/journal.yaml): id (ulid), timestamp, proposer (llm|human), kind (assign|unassign|availability|skill_update|person_update|project_update), payload (dict), status (pending|applied|rejected), applied_at, rejected_reason.

YAML files: data/skills.yaml, data/people.yaml (skills embebidas), data/projects.yaml, data/assignments.yaml, data/availability.yaml, data/offices.yaml, data/journal.yaml.
sync: idempotente. Diff destructivo (entidad borrada con referencias vivas) exige --confirm. Sin --confirm, exit ≠ 0 con diff legible. make up llama a sync sin --confirm y solo fuerza interactivo si detecta destructivo real.
2. Backend API (FastAPI)
Auth: X-API-Key desde .env (autogenerado en make install, escrito a .env, anunciado en consola). CORS para http://localhost:3000, http://localhost:3001, http://<host-ip>:3000. Timeout httpx a Ollama: 180s. Logging loguru a logs/app.log rotado (10MB, 7 días). Registra tool-calls, journal creates, applies, rejects, syncs destructivos.
Endpoints:
GET  /api/health
GET  /api/people
GET  /api/people/{id}
GET  /api/people/{id}/skills
GET  /api/people/{id}/coherence
GET  /api/coherence
GET  /api/skills
GET  /api/projects?status=active|pipeline|closed
GET  /api/projects/{code}
GET  /api/assignments?week=YYYY-Www&person_id=&project_code=
GET  /api/heatmap?start=YYYY-MM-DD&end=YYYY-MM-DD
GET  /api/skill-gap?scope=pipeline|active
GET  /api/availability?week=YYYY-Www
GET  /api/geo
GET  /api/search?q=...
GET  /api/journal?status=pending|applied|rejected
POST /api/journal
POST /api/journal/{id}/apply
POST /api/journal/{id}/reject   body: {reason}
GET  /api/notes?person_id=|project_code=
POST /api/notes
POST /api/chat                  SSE streaming, tool-loop server-side
Respuestas JSON con shapes listos para consumo frontend, sin transformación. Esquemas formalizados con pydantic v2 para que se puedan derivar tipos TS (generación manual en web/lib/types.ts, mantenidos en paralelo; documentado en PLAN.md como deuda consciente V2: generación automática con datamodel-code-generator u OpenAPI).
3. Capa LLM (Llama 3.1 8B vía Ollama nativo)
Cliente HTTP directo a http://localhost:11434/api/chat desde api/routes/chat.py. Sin ollama-python. Llama nativo soporta tools; usar tools param. Tool-loop server-side, máx 5 iteraciones por turno. Streaming obligatorio: el endpoint POST /api/chat devuelve SSE (text/event-stream) con eventos tipados token, tool_call, tool_result, done, error. El frontend en /chat lee el stream y renderiza incremental.
Tools (nombres cortos, definiciones inline en agent/tools.py que llaman a core/queries):

find_people(filters) — skill_id, min_level, city, office, available_week, global_level.
get_person(alias_or_id).
get_project(code).
who_is_free(week, min_pct_free=50).
skill_gap(scope).
propose_assignment(person_id, project_code, pct, start, end, role) → journal.
propose_availability(person_id, kind, start, end, pct) → journal.
propose_skill_update(person_id, skill_id, level, growth_interest?) → journal.
add_note(entity_type, entity_id, body, tags) → directo.
list_pending_journal().

System prompt en agent/prompts/system.md, español, directo. Deja explícito:

Solo propones con propose_*; nunca mutas directo personas/proyectos/assignments.
Notas sí son escritura directa.
Formato respuesta compacto: <id> (<city>, L<level>) — <info>.
Máx 5 tool calls por turno.
Prohibido inventar datos; si faltan, usa una tool.
Lenguaje: español neutro, directo, sin preámbulos.

Fallback: si el modelo devuelve texto sin tool válida pero la query la requiere claramente, reintenta una vez con format: json y schema pydantic de la tool más probable según keyword match. Si falla, error legible.
3 few-shot en agent/prompts/fewshot.json (formato messages Ollama):

"¿quién tiene nivel ≥3 en hacking_active_directory y está libre la semana 47?" → find_people + who_is_free.
"Mete a santi 50% en PT-2026-014 desde el lunes y anota que es relevo de Fer" → propose_assignment + add_note + confirmación con journal id.
"¿dónde me falta gente para el pipeline?" → skill_gap(pipeline) + comentario priorizando por weight.

4. Frontend Next.js (la cara del producto, diseñado end-to-end por Claude)
Stack: Next 14 App Router + TS + Tailwind + shadcn inlined + Recharts + MapLibre GL + TanStack Query + Zod.
Sistema de diseño:

Paleta dark: slate-950 fondo base, slate-900 superficies elevadas, slate-800 bordes, slate-100 texto principal, slate-400 texto secundario. Accent: emerald-400 para positivo/acción, amber-400 para warnings de coherencia, rose-400 para errores/over-allocation. Niveles de skill visualizados con escala monocromática emerald-950 → emerald-400.
Tipografía: Inter para UI, JetBrains Mono para ids, códigos de proyecto, niveles numéricos, timestamps.
Densidad alta. Espaciado reducido. Sin decoración inútil. Radius rounded-md consistente.
Componentes consistentes: todas las tablas usan DataTable. Todos los heatmaps usan HeatmapGrid. Todos los cards de persona usan PersonCard. Esto asegura coherencia entre las 9 páginas.

Arquitectura frontend:

web/lib/api.ts: cliente tipado que habla con los proxy routes /api/* de Next, nunca directo al backend Python desde el browser.
web/app/api/[...path]/route.ts: single catch-all proxy que reenvía toda /api/* al backend http://api:8000 (dentro del compose) o http://localhost:8000 (dev fuera de compose, controlado por API_BASE_URL env server-side) añadiendo el header X-API-Key. Proxy también para SSE: stream pass-through bien configurado.
web/lib/types.ts: tipos TS derivados de los schemas pydantic. Mantener en paralelo V1.
TanStack Query para caching y revalidación. Invalidación tras POST /api/journal/{id}/apply|reject y POST /api/notes.

9 páginas (App Router, estructura completa):

/ Overview: KPIs (nº personas, activos, pipeline count, coherence warnings count, carga media de la semana actual). Heatmap compacto semana actual. Top 3 gaps del pipeline. Últimas 5 entradas del journal. Acceso rápido a las otras páginas.
/people People: tabla con filtros (office, city, global_level, skill + min_level). Click en fila abre un Sheet (drawer) con detalle completo: info básica, skills en SkillRadar, assignments activas, notas recientes, CoherenceWarnings.
/people/[id] Person detail: página dedicada para enlaces permanentes. Mismo contenido que el drawer, más notas paginadas.
/projects Projects: tres columnas por status. Cada ProjectCard muestra tipo, ventana, % cobertura de required_skills, assignments actuales.
/projects/[code] Project detail: required_skills con gap vs equipo, assignments actuales, timeline visual, notas.
/schedule Schedule: HeatmapGrid completo, filas = personas, columnas = semanas, celdas coloreadas por dedication_pct. Filtro por rango de semanas. Click en celda → popover con breakdown de proyectos esa semana para esa persona. Indicador visible cuando suma > 100%.
/skills Skills: dos vistas toggleables. (a) Matriz equipo × skills con niveles por celda. (b) Skill gap matrix: skills requeridas por pipeline vs skills disponibles actuales, déficit destacado en rose-400.
/map Map: MapLibre con tiles OSM, markers por oficina, popover con personas de esa oficina al hacer click.
/journal Journal: inbox. Tabs pending | applied | rejected. Cada JournalItem muestra kind, payload renderizado legible (no JSON raw), proposer, timestamp. Botones Apply y Reject (diálogo con razón). Tras acción: invalidar queries relevantes y refrescar.
/chat Chat: UI conversacional. Mensajes del usuario y del asistente diferenciados. ToolCallBlock colapsable con entrada y salida de cada tool, renderizado inline cuando el stream los emite. Streaming de tokens visible. Si el turno genera journal entries, banner al final con link directo a /journal.
/search Search: input global FTS. Resultados agrupados por tipo (personas, proyectos, notas).

Son 11 rutas contando las 2 de detalle (/people/[id], /projects/[code]). Si cuentas solo secciones top-level de la sidebar, son 9: Overview, People, Projects, Schedule, Skills, Map, Journal, Chat, Search.
Sidebar fija a la izquierda con estas 9 secciones, ids en JetBrains Mono, iconos de lucide-react. Layout desktop-first. Mobile usable pero no prioritario.
Componentes reutilizables en web/components/:

DataTable (sortable, filterable, genérico).
HeatmapGrid (reutilizable schedule/skills matrix).
PersonCard, ProjectCard.
JournalItem.
ChatMessage, ToolCallBlock, StreamingText.
SkillRadar (Recharts RadarChart).
CoherenceWarnings.
Sidebar, PageHeader, StatusBadge, LevelBadge, KPICard.
ui/ (shadcn inlined: button, card, sheet, dialog, tabs, table, input, select, badge, toast).

5. CLI + Makefile (botón gordo)
CLI (typer + rich):

init, sync [--confirm], validate, serve [--port], chat, journal list|apply <id>|reject <id> --reason, seed, doctor.
doctor verifica: Ollama reachable, llama3.1:8b pulled, Docker corriendo, YAML válido, SQLite consistente, webapp respondiendo, puertos libres o ajustados, API key presente. Output por item verde/rojo con mensaje accionable.

Makefile (botón gordo, todos idempotentes y resumibles):
make install    # verifica Ollama, pulla llama3.1:8b si falta, autogenera .env con API_KEY,
                # python deps, npm ci en web/, build web producción
make up         # compose up -d, detecta conflicto de puertos y ajusta, healthchecks,
                # anuncia URLs finales (http://<host-ip>:<port>)
make down
make chat       # CLI REPL; si api down la levanta antes
make dash       # open http://<host>:<port-resuelto>
make seed
make doctor
make logs       # tail logs/app.log + logs de compose
make reset      # wipe SQLite, regenera desde YAML; confirmación interactiva explícita
make test       # pytest + web vitest + tsc --noEmit
Resolución de puertos: make up checkea 3000 y 8000; si ocupados sube al siguiente libre, escribe WEB_PORT/API_PORT a .env.local, los lee el compose vía interpolación. Imprime banner con las URLs resueltas.
6. Despliegue red interna
Compose en red bridge. web publica ${WEB_PORT}:3000, api publica ${API_PORT}:8000 para debug directo pero el acceso normal es por la webapp. Healthchecks: web depende de api healthy. api health check contra /api/health. Variables: API_KEY, API_BASE_URL=http://api:8000 (interno compose), OLLAMA_URL=http://host.docker.internal:11434 (o la IP del host configurable; en Linux requiere --add-host=host.docker.internal:host-gateway en el service api).
README incluye instrucciones claras para:

Ejecución local desarrollo (Ollama en host, compose corriendo, acceso http://localhost:<port>).
Despliegue en red interna MSSP (servidor interno con Docker y Ollama, acceso desde estaciones de trabajo por http://<server-ip>:<port>).
Firewall interno: solo puerto WEB_PORT abierto a la LAN. API_PORT restringido a localhost del servidor si se quiere.

7. Arquitectura del repo
core/
  models.py, db.py, sync.py, validate.py, queries.py, yaml_io.py, logging_setup.py
api/
  main.py, deps.py
  routes/
    health.py, people.py, skills.py, projects.py, assignments.py,
    heatmap.py, skill_gap.py, availability.py, geo.py, search.py,
    notes.py, journal.py, coherence.py, chat.py
agent/
  llm.py, tools.py
  prompts/ system.md, fewshot.json
cli.py
data/           # YAML source-of-truth
notes/
  persons/
  projects/
logs/
tests/
  test_validate.py
  test_sync.py
  test_apply_journal.py
  test_coherence.py
  test_api_smoke.py
web/
  app/
    layout.tsx
    page.tsx                    # Overview
    people/
      page.tsx
      [id]/page.tsx
    projects/
      page.tsx
      [code]/page.tsx
    schedule/page.tsx
    skills/page.tsx
    map/page.tsx
    journal/page.tsx
    chat/page.tsx
    search/page.tsx
    api/
      [...path]/route.ts        # proxy catch-all con SSE support
  components/
    Sidebar.tsx, PageHeader.tsx, KPICard.tsx,
    DataTable.tsx, HeatmapGrid.tsx, SkillRadar.tsx,
    PersonCard.tsx, ProjectCard.tsx, JournalItem.tsx,
    ChatMessage.tsx, ToolCallBlock.tsx, StreamingText.tsx,
    CoherenceWarnings.tsx, StatusBadge.tsx, LevelBadge.tsx,
    ui/   # shadcn inlined
  lib/
    api.ts, types.ts, utils.ts, query-client.ts, sse.ts
  styles/ globals.css
  tests/
    smoke.test.tsx
  tailwind.config.ts, tsconfig.json, next.config.mjs, postcss.config.mjs,
  package.json
Dockerfile.api
Dockerfile.web
docker-compose.yml
Makefile
.env.example
pyproject.toml
README.md
PLAN.md
OPEN_QUESTIONS.md
API, CLI, agent consumen core/queries.py. Cero duplicación.
8. Tests — casos concretos, no smoke
test_validate.py:

Seed válido → 0 errores, ≥1 warning (tbd_03 senior con skills flojas dispara insufficient_skill_coverage).
Skill id fuera de catálogo → error bloqueante.
Assignment dedication_pct=120 → error.
Suma assignments + availability para persona/semana >100 → error.

test_sync.py:

Dos syncs consecutivos idempotentes (hash SQLite estable).
Borrar persona con assignments en YAML + sync sin --confirm → exit ≠ 0 con diff.
Con --confirm → aplica.

test_apply_journal.py:

propose_assignment crea entry pending con ulid.
apply muta YAML preservando comentarios (test con comentarios plantados en seed).
last_used_on_project actualizado solo en skills que matchean required_skills del proyecto.
ruamel fallando (fichero corrupto simulado) → .bak restaurado, error claro.

test_coherence.py:

senior con 2 skills L4 + top-5 avg 3.6 → sin warning.
senior con 1 skill L4 → warning.
master con 4 skills registradas → insufficient_skill_coverage.
junior con 3 skills L4 → warning.

test_api_smoke.py:

/api/health 200.
/api/people sin auth → 401.
/api/people con auth → 200 y shape correcta.
POST /api/journal → entry con ulid.
POST /api/journal/{id}/apply en pending → status=applied, applied_at poblado.
SSE /api/chat emite eventos bien formados en un prompt determinista (mock Ollama con respuesta fija).

web/tests/smoke.test.tsx (Vitest):

lib/api.ts tipa correctamente las responses contra un mock del backend.
Route handler proxy forma URLs correctas y reenvía header X-API-Key.
HeatmapGrid renderiza N filas y M columnas para un input dado.
ChatMessage renderiza streaming incremental simulando tokens SSE.

9. Seed realista (plantar en los YAML):

6 personas:

fer Madrid, senior, CTI + pentesting. Skills coherentes (L≥3 en osint, reporting, hacking_web, hacking_active_directory, automatizacion_tooling), last_used_on_project populado.
santi Madrid, senior, pentesting heavy. Skills coherentes (L≥3 en hacking_web, hacking_active_directory, escalada_privilegios, pivoting_movimiento_lateral, reporting).
tbd_01 Barcelona, intermediate, pentesting web.
tbd_02 Barcelona, intermediate, red team incipiente.
tbd_03 remote, marcado senior pero skills flojas → dispara warning deliberado.
tbd_04 Lisboa, junior recién entrado.


8 proyectos: 5 active, 3 pipeline. Tipos variados.
Assignments cubren 4 semanas desde hoy. Incluir deliberadamente una suma >100% en una semana concreta para validar el test.
1 PTO programado, 1 training.
journal.yaml: 2 applied (histórico), 1 pending (vivo para demo).
Notas: al menos 1 entry en notes/persons/fer.md y 1 en notes/projects/<code>.md.
</tarea>


<constraints>
- Local. Compose orquesta `api + web`. Ollama nativo en host.
- Backend código/comentarios en inglés. Mensajes CLI, respuestas LLM, UI de la webapp (labels, textos, mensajes de error mostrados al usuario) en **español**.
- Deps Python: `pydantic>=2`, `fastapi`, `uvicorn[standard]`, `typer`, `ruamel.yaml`, `httpx`, `python-dateutil`, `rich`, `loguru`, `python-ulid`, `pytest`, `pytest-asyncio`. SQLite stdlib + FTS5. Sin ORM. Sin `pyyaml`.
- Deps Web: `next@14`, `react@18`, `typescript`, `tailwindcss`, `@radix-ui/*` (primitives para shadcn inlined), `class-variance-authority`, `clsx`, `tailwind-merge`, `lucide-react`, `recharts`, `maplibre-gl`, `@tanstack/react-query`, `date-fns`, `zod`. Dev: `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `jsdom`, `eslint`.
- shadcn components inlined como ficheros TSX escritos directamente. No `npx shadcn add` en `make install`.
- Clientes siempre con `client_alias`. Nunca nombres reales en el repo.
- Zero "actúa como" en prompts internos.
- `ruamel.yaml` con `YAML(typ='rt')`.
- `validate` estricto en errores, permisivo en warnings.
- Makefile idempotente. Cada target robusto si se llama dos veces.
- Streaming SSE en `/api/chat` es obligatorio V1.
- Conflicto de puertos autoresuelto con banner informativo.
- Dark-only V1.
- Sin autenticación de usuarios en la webapp; solo API key backend.
- API key jamás en bundle cliente; siempre vía route handler server-side.
- MapLibre con tiles OSM raster públicos, sin token.
- Si algo huele a sobre-ingeniería para 6 personas, va a `OPEN_QUESTIONS.md` con propuesta reducida. No decidas unilateralmente ampliar alcance.
- No inventes campos, endpoints ni páginas que no estén en este brief. Lo que falte, a `OPEN_QUESTIONS.md`.
</constraints>
<formato_de_salida>
Exacto este orden. Claude Code terminal, sin límite por turno.

PLAN.md — 18–25 bullets. Fases de build en orden (backend → seed → tests Py → sistema de diseño + layout → páginas en orden: Overview, People, Projects, Schedule, Skills, Map, Journal, Chat streaming, Search → tests web → compose + deploy interno → polish). Decisiones clave con justificación (webapp propia full-stack, Next 14 App Router + proxy catch-all para API key, streaming SSE obligatorio, dark-only, shadcn inlined, Ollama nativo host, journal, ruamel, auto-update last_used_on_project, warnings no-bloqueantes, puertos autoresueltos, botón gordo). Riesgos conocidos. Trade-offs. V2 backlog (auth usuarios si sale de LAN, responsive móvil, theming light, generación auto de tipos TS desde OpenAPI, Playwright E2E).
Árbol completo del repo, anotado, una línea por fichero/carpeta relevante.
Código completo runnable, en este orden:

Backend data: data/skills.yaml, data/offices.yaml, data/people.yaml, data/projects.yaml, data/assignments.yaml, data/availability.yaml, data/journal.yaml.
core/models.py, core/db.py, core/sync.py, core/validate.py, core/queries.py, core/yaml_io.py, core/logging_setup.py.
api/main.py, api/deps.py, cada fichero en api/routes/ incluyendo chat.py con SSE.
agent/tools.py, agent/llm.py, agent/prompts/system.md, agent/prompts/fewshot.json.
cli.py.
tests/* (5 ficheros con casos concretos).
Web config: web/package.json, web/tsconfig.json, web/next.config.mjs, web/tailwind.config.ts, web/postcss.config.mjs.
Web core: web/styles/globals.css, web/lib/utils.ts, web/lib/api.ts, web/lib/types.ts, web/lib/query-client.ts, web/lib/sse.ts.
Web shadcn inlined en web/components/ui/: button.tsx, card.tsx, sheet.tsx, dialog.tsx, tabs.tsx, table.tsx, input.tsx, select.tsx, badge.tsx, toast.tsx, skeleton.tsx.
Web components compartidos: todos los listados arriba.
Web layout y páginas: web/app/layout.tsx, web/app/api/[...path]/route.ts, web/app/page.tsx, y las 10 páginas restantes.
web/tests/smoke.test.tsx.
Infra: Dockerfile.api, Dockerfile.web, docker-compose.yml, Makefile, .env.example, pyproject.toml.


README.md:

Intro 3 líneas: qué es y para quién.
Prerequisitos: Docker + Docker Compose, Python 3.11+, Node 20+, Ollama nativo instalado en el host con llama3.1:8b (el pull lo hace make install).
Quickstart botón gordo: make install && make up && make seed. Abrir la URL anunciada en banner.
Rúbrica skills 1–5 y niveles globales con reglas de coherencia (copiadas del brief).
Tour de la webapp: 1 línea por cada una de las 9 secciones de la sidebar.
Flujo 1 — CLI puro: editar YAML a mano, validate, sync, serve, curl de ejemplo.
Flujo 2 — chat con Llama (desde la webapp /chat o desde REPL): ejemplo de sesión completa con tool-calls visibles y un journal apply desde /journal.
Despliegue en red interna MSSP: pasos concretos en un servidor con Docker+Ollama, acceso desde estaciones por IP.
Tabla de endpoints con request y response de ejemplo.
Troubleshooting 7 puntos: Ollama no reachable, puertos ocupados (explicación de auto-resolve), API key perdida, SQLite corrupta (make reset), webapp no conecta al backend, journal apply falla, streaming se corta.


OPEN_QUESTIONS.md — descripciones de skills pendientes (bloqueante suave), fricción journal a evaluar tras 2 semanas, riesgo tool-calling Llama 3.1 8B y cuándo saltar a Qwen 2.5 7B, autenticación de usuarios si sale de LAN, deuda de mantener web/lib/types.ts en paralelo a pydantic (V2: generación auto), responsive móvil V2, theming light V2, Playwright E2E V2, reindex FTS incremental si crece volumen, tiles OSM para producción real, backup strategy de data/ (git pero V2 backup automático programado).
</formato_de_salida>

<estilo>
Denso, directo, canalla técnico. Sin preámbulos, sin emojis, sin cierres. Señala decisiones discutibles inline. Sobre-ingeniería → OPEN_QUESTIONS. No rellenes vacíos con plausibilidad.
</estilo>
</prompt>