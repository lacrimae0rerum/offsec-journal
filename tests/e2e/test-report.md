# OffSec Journal — Informe E2E

## Ejecución 10 — 2026-06-21 18:50 UTC — Fix flakiness 06-search

### Resumen

| Métrica | Valor |
|---|---|
| Total tests (no-@write) | 81 |
| Pasados | 81 (×3 corridas consecutivas) |
| Fallidos | 0 |
| Saltados | 0 |
| Duración | ~14 s |

**Estado: VERDE y estable.** Una corrida inicial dio 1 fallo intermitente en
`06-search.spec.js:67` ("Filtrar por tipo incluye types"); pasaba en aislamiento → flaky
bajo carga (9 workers), no bug de la app.

### BUG-E2E-020 — flakiness en filtro por tipo

**Causa:** el test rellenaba `#search-input` con "fer" *antes* de desmarcar checkboxes;
cada `uncheck` con query no vacía dispara una búsqueda `onchange`, y el `waitForResponse`
podía capturar la del último uncheck (0 tipos → URL sin `types=`) en vez de la del Enter.
**Fix:** configurar los checkboxes primero (con input vacío `runSearch()` hace skip, sin
búsquedas intermedias), luego rellenar la query y pulsar Enter; además el `waitForResponse`
exige ahora `types=` en la URL. Verificado: 81/81 en 3 corridas seguidas.

---

## Ejercicio del journal — Round 2 — 2026-06-21 18:20 UTC (`scripts/coverage_round2.py`)

Dos objetivos: (1) dar carga **actual/futura** a todas las personas — el seed tenía
ventanas Feb-Abr 2026 (pasadas respecto a hoy 21-jun), por lo que 7 de 10 personas
aparecían sin asignación activa en las vistas de "ahora"; (2) casos límite más agresivos.

Resultado: 23 OK, 1 rechazo correcto, **9 hallazgos**. Tras limpiar la basura aplicada:
**10 personas / 10 proyectos / 4 clientes activos, 0 warnings, 0 pending, y NINGUNA
persona sin carga actual/futura** (4 proyectos nuevos con ventanas Jul-Dic + 9 asignaciones).

### 🐛 BUG-APP-003 — el journal no valida el formato de id/code (sin corregir)

Los modelos de **lectura** exigen regex (`person.id` → `^[a-z][a-z0-9_]*$`,
`project.code` → `^[A-Z]{2,4}-\d{4}-\d{3}$`) pero los **payloads del journal**
(`api/models/journal.py`) declaran `id: str` / `code: str` sin patrón. Se aceptan y
aplican:
- `person_create` id `"Bad Id!"` y `"123abc"`.
- `project_create` code `"bad-code"` y `"ACM-26-1"`.
- `skill_catalog_create` id `"Not Snake"` (debería ser snake_case).

Entran entidades con id/code malformado que luego pueden romper enlaces, búsquedas o
los propios modelos de lectura. **Fix:** replicar los `Field(pattern=...)` en los
payloads de create.

### 🐛 BUG-APP-004 — campos de texto requeridos aceptan vacío (sin corregir)

`person_create` con `full_name=""` y `client_create` con `name=""` se aceptan y aplican.
**Fix:** `Field(min_length=1)` (o validador de no-vacío tras strip) en los campos
obligatorios de texto.

### ⚠️ BUG-APP-005 / hallazgo — sin regla de sobre-asignación

Carla quedó al **130%** (70% NMB-2026-002 + 60% VTX-2026-002 solapados Jul-Sep) y
`/api/coherence` **no emite ninguna advertencia**. No existe regla que detecte dedicación
agregada > 100% en ventanas solapadas. (También observado en round 1 con Hugo.) **Fix:**
añadir regla de coherencia de over-allocation por ventana temporal.

### 📝 Menor — email de contacto sin validar

`contact_add` acepta `email="not-an-email"`. Campo `str` libre; podría usar `EmailStr`.

### ✓ Casos válidos poco comunes (aceptados correctamente)

Ventana de un solo día (`window_start==window_end`), assign 0% mismo día, reactivación de
asignación archivada (unassign→assign mismo triple revive la fila), `skill_update` level 0,
nombre con tildes/Unicode. Y `assign` a persona archivada → rechazado correctamente.

---

## Ejecución 9 — 2026-06-21 17:55 UTC — Tras fix BUG-APP-002 + validación temprana

### Resumen

| Métrica | Valor |
|---|---|
| Total tests (no-@write) | 81 |
| Pasados | 81 |
| Fallidos | 0 |
| Saltados | 0 |
| Duración | 44.4 s |

**Estado: VERDE.** Contenedor reconstruido con los fixes de validación del journal
(BUG-APP-002: fechas invertidas + validación temprana de duplicados/índices/assign/
unassign). pytest backend: 209 verdes. `exercise_journal.py`: 0 hallazgos sospechosos.

> Dataset: 10 personas / 6 proyectos / 4 clientes, 0 warnings de coherencia, 0 pending.
> Funcionalidades verificadas: ídem ejecución 8 (cobertura UI completa con datos reales).

---

## Ejercicio exhaustivo del journal — 2026-06-21 17:20 UTC (`scripts/exercise_journal.py`)

Objetivo: ejercitar **los 22 kinds del journal** (no solo los 8 del seed) por la API
real y disparar casos límite para cazar bugs. **Cobertura lograda: 22/22 kinds aplicados.**
Resultado: 21 OK, 9 rechazos correctos en create, **12 hallazgos sospechosos**.

Dataset restaurado a estado coherente tras el ejercicio: 10 personas / 6 proyectos /
4 clientes activos, **0 warnings de coherencia, 0 pending** (entidades de prueba `zz_*`
archivadas; datos basura de los bugs limpiados).

### 🐛 BUG-APP-002 — rangos de fecha invertidos se aceptan y aplican (CLARO, sin corregir)

`assign`, `availability` y `project_create` aceptan **y aplican** rangos con la fecha de
fin anterior a la de inicio, sin validación en create ni en apply. Entran datos
semánticamente inválidos que afectan a heatmap, disponibilidad y cálculos de carga.

- `assign` ana→INT con `start=2026-05-01, end=2026-04-01` → aplicado (HTTP 200/200).
- `availability` pto `start=2026-05-10, end=2026-05-01` → aplicado.
- `project_create` `window_start=2026-06-01, window_end=2026-05-01` → aplicado.

**Causa:** los modelos Pydantic (`api/models/journal.py`) validan formato de fecha pero
no el orden; no hay validador `start <= end` ni en el modelo ni en los handlers.
**Fix sugerido:** validador de orden en `AssignPayload`/`AvailabilityPayload`/
`ProjectCreatePayload` (y *Update*), devolviendo 400 en create.

### ⚠️ Patrón de validación tardía (9 casos, mismo patrón que BUG-APP-001)

Estos se aceptan en create (200) y solo fallan al aplicar — **pero con mensaje legible**
(no opaco). Decisión de diseño discutible: `_check_referenced_entities` valida refs
cruzadas en create, pero estas validaciones viven solo en el handler (apply):

- Duplicados: `person_create`, `client_create`, `project_create`, `office_create`,
  `skill_catalog_create` con id/code ya existente.
- `assign` duplicado (mismo person/project/start activo).
- `unassign` sin asignación activa que coincida.
- `contact_update` / `contact_remove` con `contact_index` fuera de rango.

Generan entradas pending inaplicables hasta que el operador las rechaza. Menos grave que
BUG-APP-001 (mensajes claros). Opción: subir estas comprobaciones a create para feedback
inmediato y evitar pending huérfanas.

### 📝 Hallazgo menor — disponibilidad no editable/borrable

No existe ningún kind para borrar o editar una disponibilidad: `availability` solo hace
append. Un PTO/baja erróneo no se puede deshacer por el journal (hubo que editar el YAML
a mano para limpiar el dato basura del BUG-APP-002).

### ✓ Rechazos correctos en create (9)

Validados temprano y bien: refs inexistentes (`assign` persona/proyecto, `person_update`),
`assign` a proyecto archivado, límites numéricos Pydantic (`dedication_pct` 0-200,
`level` 0-5, `pct` 0-100) y enums inválidos (`availability_kind`, `role`).

---

## Ejecución 8 — 2026-06-21 16:48 UTC — Tras rebuild Docker

### Resumen

| Métrica | Valor |
|---|---|
| Total tests (no-@write) | 81 |
| Pasados | 81 |
| Fallidos | 0 |
| Saltados | 0 |
| Duración | 15.0 s |

**Estado: VERDE — cobertura total estable.** Imagen Docker reconstruida (`docker compose
up -d --build`) para servir el código actual del repo/GitHub (estaba 5 días desfasada);
el seed sobrevivió porque `data/` y `notes/` son bind mounts.

**BUG-APP-001 reverificado tras el rebuild: PERSISTE.** `skill_update` con `skill_id`
inexistente sigue devolviendo 200 en el create y fallando en apply con
`FOREIGN KEY constraint failed`. No estaba corregido en GitHub. Sin corregir aún.

> Funcionalidades verificadas: ídem ejecución 7 (cobertura completa con datos reales).

---

## Ejecución 7 — 2026-06-21 16:10 UTC — Poblado completo + cobertura total

### Resumen

| Métrica | Valor |
|---|---|
| Total tests (no-@write) | 81 |
| Pasados | 81 |
| Fallidos | 0 |
| Saltados | 0 |
| Duración | 14.4 s |

**Estado: VERDE — cobertura total. La BD se pobló con datos permanentes, así que
los 14 tests que antes saltaban por BD vacía ahora se ejecutan de verdad y pasan.**

### Población de datos (script `scripts/seed_demo.py`)

Seed realista de un equipo offsec, creado vía la API HTTP real (mismo camino que la
SPA) con manejo del rate limit (60 escrituras/min). Datos **permanentes** (no se
archivan). 89 operaciones OK de 90.

- 4 clientes (banca, salud, retail, sector público) + 5 contactos
- 10 personas en Madrid/Barcelona/Lisboa/Remote, niveles y FTE variados (0.5/0.8/1.0)
- ~52 skills asignadas (niveles 1-5, growth_interest)
- 6 proyectos (web/infra/red_team/internal) con required_skills + min_level
- 13 asignaciones (lead/executor/reviewer/shadow)
- 6 disponibilidades (pto/sick/training/overhead/hold)
- 4 notas + 1 skill nueva en catálogo
- Estado final: **0 warnings de coherencia, 0 entradas pending**

### Bug de la APP detectado — BUG-APP-001

**Kind:** `skill_update` con un `skill_id` que no existe en el catálogo de skills.
**Síntoma:** `POST /api/journal` devuelve **HTTP 200** y crea la entrada `pending`; el
fallo solo aparece en `POST /api/journal/{id}/apply` con un error opaco:
`apply failed: FOREIGN KEY constraint failed`.
**Causa raíz:** `_check_referenced_entities()` (`api/core/journal.py:583`) valida las
referencias cruzadas de `assign`, `person_*`, `project_*`, `client_*`, `contact_*` y
`unassign`, pero **no valida `skill_id` en `skill_update`** (ni `required_skills` en
project, ni `skill_id` en `skill_label_update`/`skill_catalog_archive`).
**Impacto:** se acumulan entradas `pending` huérfanas e inaplicables; el operador
recibe un error de bajo nivel en vez de un 400 legible en el create.
**Recomendación:** añadir a `_check_referenced_entities` la comprobación de que
`payload["skill_id"]` existe (no archivado) en `data/skills.yaml` para `skill_update`,
y análogamente validar los `skill_id` de `required_skills` en `project_create/update`.
**Clasificación:** bug real de la app (validación tardía). NO corregido aún — pendiente
de decisión.

### Falso positivo descartado

Inicialmente pareció que `GET /api/journal` devolvía `payload` vacío en las entradas
pending. Es falso: la clave es `payload_json` (string JSON) y contiene el payload
íntegro. Sin bug.

### Bugs de la SUITE corregidos (los 5 fallos al poblar) — BUG-E2E-016..019

Al poblar la BD, los 14 tests que saltaban se ejecutaron; 5 fallaron, **todos por
desajuste selector/lógica del test con el DOM real (ninguno bug de la app)**, según
diagnóstico contra `web/{index.html,app.js}`:

- **BUG-E2E-016** (`02-people` ×varios): `#people-tbody tr` resolvía al placeholder
  `<tr>Sin resultados</tr>` (sin handler) durante el re-render que dispara
  `refreshAll()`. Fix: `#people-tbody .people-row` (el `.click()` auto-espera al
  re-render real). El handler del drawer está en `.people-row` (`app.js:527`).
- **BUG-E2E-017** (`02-people:69`): `#page-person-detail .tabs .tab` no existe — esa
  página no usa pestañas, sino tarjetas `.wf-card` apiladas. Fix: contar `.wf-card`.
- **BUG-E2E-018** (`03-projects:47/70`, `10-notes:52`): la vista por defecto de
  proyectos es Kanban (la tabla arranca `display:none`), así que `#projects-tbody tr`
  existe pero no es visible; la rama `if (isVisible())` era one-shot y caía al `else`
  oculto por la carrera de re-render. Fix: esperar `.kanban-card` visible y clicarla.
- **BUG-E2E-019** (`04-clients:32`): la clase real de cada item es `.client-list-item`
  (`app.js:732`), no `.list-item`. Fix: selector corregido.
- Bonus (`10-notes:32`): rama muerta que buscaba una pestaña de notas inexistente;
  ahora verifica directamente `#person-detail-notes` (siempre visible).

**Patrón de fondo:** los tests clicaban elementos one-shot sin esperar al re-render que
`refreshAll()` ejecuta tras `bootApp`. La cura general es localizar la clase real del
elemento con handler y dejar que el auto-wait de Playwright espere su aparición.

---

## Ejecución 6 — 2026-06-21 15:46 UTC

### Resumen

| Métrica | Valor |
|---|---|
| Total tests (no-@write) | 81 |
| Pasados | 67 |
| Fallidos | 0 |
| Saltados (BD vacía) | 14 |
| Duración | 13.1 s |

**Estado: VERDE — suite estable, sin regresiones.**

> Tests saltados: mismos 14 por BD vacía (sin cambios desde ejecución 5).
> Funcionalidades verificadas: ídem ejecución 5.

---

## Ejecución 5 — 2026-06-21 13:15 UTC

### Resumen

| Métrica | Valor |
|---|---|
| Total tests (no-@write) | 81 |
| Pasados | 67 |
| Fallidos | 0 (1 detectado y corregido en esta iteración) |
| Saltados (BD vacía) | 14 |
| Duración | 16.1 s |

**Estado: VERDE tras fix en caliente.**

### Bug detectado y corregido — BUG-E2E-015

**Test:** `Filtrar por tipo incluye el parámetro types en la URL`  
**Error:** `expect(received).toContain('types=')` — URL recibida: `?q=fer` (sin `types=`)  
**Causa raíz:** `page.keyboard.press('Enter')` dispara sobre el checkbox que tiene el foco tras el loop de uncheck/check, no sobre `#search-input`. El checkbox con foco recibe Enter (que lo desmarca), y `runSearch()` se dispara sin ningún tipo seleccionado → `types=[]` → sin parámetro en la URL. Mismo patrón que BUG-E2E-013 (date_to).  
**Fix:** Cambiado a `page.press('#search-input', 'Enter')` para garantizar que Enter se dispara sobre el input de búsqueda independientemente del foco.  
**Clasificación:** Bug de la suite de tests (no de la app).

> Tests saltados: mismos 14 por BD vacía.

---

## Ejecución 4 — 2026-06-21 12:19 UTC

### Resumen

| Métrica | Valor |
|---|---|
| Total tests (no-@write) | 81 |
| Pasados | 67 |
| Fallidos | 0 |
| Saltados (BD vacía) | 14 |
| Duración | 13.9 s |

**Estado: VERDE — 0 fallos. Resultado idéntico al run anterior — suite estable.**

> Tests saltados: mismos 14 por BD vacía (sin cambios desde ejecución 3).
> Funcionalidades verificadas: ídem ejecución 3.

---

## Ejecución 3 — 2026-06-21 11:47 UTC

### Resumen

| Métrica | Valor |
|---|---|
| Total tests (no-@write) | 81 |
| Pasados | 67 |
| Fallidos | 0 |
| Saltados (BD vacía) | 14 |
| Duración | 13.5 s |

**Estado: VERDE — 0 fallos.**

---

### Tests saltados (14) — causa: BD de desarrollo vacía

Todos los skips tienen guards explícitos (`apiGet + test.skip()`). Se activarán cuando la BD tenga datos.

| Test | Motivo |
|---|---|
| La tabla de personas carga al menos una fila | `people: 0` |
| Click en una fila abre el drawer de persona | `people: 0` |
| El drawer se cierra con el botón ✕ | `people: 0` |
| El drawer muestra radar, skills y assignments | `people: 0` |
| El enlace "Ver página completa" navega al person-detail | `people: 0` |
| Las pestañas del detalle de persona existen | `people: 0` |
| El botón + PTO / training está en el detalle de persona | `people: 0` |
| El modal de disponibilidad (PTO) requiere seleccionar persona primero | `people: 0` |
| El detalle de proyecto muestra título y breadcrumb | `projects: 0` |
| El modal de edición se puede abrir desde el detalle de proyecto | `projects: 0` |
| Hacer click en un cliente carga su detalle | `clients: 0` |
| Las cabeceras de la matriz corresponden a skills del catálogo | `people: 0` (matriz requiere personas) |
| La sección de notas de person-detail carga | `people: 0` |
| El textarea de notas del proyecto es funcional | `projects: 0` |

---

### Bugs detectados (app)

Ninguno nuevo en esta ejecución. Los bugs anteriores de la suite están corregidos.

---

### Funcionalidades verificadas correctamente

#### API (capa HTTP)
- `GET /health` → `{ok: true, version: "0.1.0"}` ✓
- `GET /api/auth/me` → autentica como `fer` (admin) ✓
- Todos los endpoints de catálogo (`/people`, `/projects`, `/clients`, `/skills`, `/offices`, `/coherence`, `/geo`, `/journal`) → HTTP 200 ✓
- Sin cabecera `Remote-User` → 401 en todos los endpoints protegidos ✓
- `GET /api/heatmap?start=...&end=...` → responde `{weeks, people}` ✓
- `GET /api/skill-gap?scope=pipeline` → array JSON ✓
- `GET /api/geo` → array JSON ✓
- `GET /api/search?q=fer` → objeto con propiedad `people` ✓
- `GET /api/admin/users` → lista con usuario `fer` ✓
- `GET /api/notes?entity_type=person&entity_id=fer` → array JSON ✓

#### UI (capa SPA)
- Overview: página activa al cargar, badge usuario, heatmap presente, coherence warnings, journal reciente, 9 botones de rango ✓
- Overview: overlay no-access NO visible para `fer` ✓
- People: filtros office/level/skill presentes, botón + Nueva persona, modal nuevo abre/cierra ✓
- Projects: pestañas de status (Kanban/Tabla), KPI activos, kanban/tabla presentes, botón + Nuevo proyecto, modal abre/cierra ✓
- Clients: sección carga, panel lista presente (adjunto al DOM), botón + Nuevo cliente, modal abre/cierra ✓
- Journal: página carga con pestañas, contenedor entries presente, pestaña Pending activa por defecto, cambio a Applied/Rejected funciona ✓
- Search: página carga, input presente, filtros presentes, >1 checkbox de tipo, filtros de fecha presentes, botón Limpiar filtros ✓
- Search: buscar "fer" llama a `/api/search?q=fer` y muestra resultados ✓
- Search: filtrar por tipo incluye `types=` en URL ✓
- Search: filtrar por fechas incluye `date_from=` y `date_to=` en URL ✓
- Search: Limpiar filtros resetea los campos de fecha ✓
- Admin: página carga, tabla usuarios tiene fila, botón + Nuevo usuario visible, modal abre/cierra ✓
- Admin: tabla auth-events visible, controles paginación prev/next/info, filtro de tipo, toggle archivados ✓
- Admin: usuario `fer` con rol `admin/member` en tabla ✓
- Skills: página carga, 2 pestañas presentes, vista matriz visible, `#skills-tbody` en DOM, botón + Nueva skill ✓
- Skills: modal nueva skill abre/cierra, vista gap accesible, skill-gap API válida ✓
- Schedule: página carga, contenedor heatmap visible ✓
- Map: página carga, contenedor mapa presente ✓
- Chat (mock): página carga, contenedor mensajes presente, sin errores JS ✓
- Notes: `/api/notes` responde array para `fer` ✓

---

## Historial de ejecuciones anteriores

### Ejecución 1 — 2026-06-21 10:45 UTC

| Métrica | Valor |
|---|---|
| Total | 87 |
| Pasados | 3 |
| Fallidos | 1 |
| TimedOut | 83 |

**Causa raíz:** Race condition en `bootApp()` — listeners de `waitForResponse` armados después de `page.goto()`. Bloqueaba todos los specs con browser.

**Bugs detectados en ejecución 1:**
- BUG-E2E-001: Race condition en `bootApp()` — listeners antes de `goto()` (**CORREGIDO**)
- BUG-E2E-002: Aserción `/health` esperaba `{status:'ok'}`, API devuelve `{ok:true}` (**CORREGIDO**)

---

### Ejecución 2 — 2026-06-21 ~11:20 UTC (estimada)

| Métrica | Valor |
|---|---|
| Total (no-@write) | 81 |
| Pasados | 57 |
| Fallidos | 12 |
| Saltados | 12 |

**Bugs detectados y corregidos entre ejecución 2 y 3:**
- BUG-E2E-003: Welcome overlay bloqueaba `goTo()` — fix: `addInitScript` con `osj_welcomed` (**CORREGIDO**)
- BUG-E2E-004: Aserciones de overview incorrectas (warnings, journal, rango buttons) (**CORREGIDO**)
- BUG-E2E-005: Admin `beforeEach` race — listener armado tras `goTo()` (**CORREGIDO**)
- BUG-E2E-006: Notes usaba `entity_type=persons`, API espera `entity_type=person` (**CORREGIDO**)
- BUG-E2E-007: Heatmap test esperaba `{weeks, rows}`, API devuelve `{weeks, people}` (**CORREGIDO**)
- BUG-E2E-008: `toHaveCountGreaterThan` no existe en Playwright 1.61.0 — sustituido por `expect(await locator.count()).toBeGreaterThan(N)` (**CORREGIDO**)
- BUG-E2E-009: Selector projects button `openModal('new-project-modal')` → `openNewProjectModal()` (**CORREGIDO**)
- BUG-E2E-010: `#clients-list` vacío tiene altura cero → `toBeVisible()` falla → cambiado a `toBeAttached()` (**CORREGIDO**)
- BUG-E2E-011: `#skills-tbody` vacío tiene altura cero → mismo fix (**CORREGIDO**)
- BUG-E2E-012: "Limpiar filtros" no limpia el input de búsqueda (diseño intencional) → test reescrito para verificar limpieza de fechas (**CORREGIDO**)
- BUG-E2E-013: `date_to` ausente en URL — `dispatchEvent('change')` disparaba búsqueda antes de setear `date_to` → usar `evaluate` sin eventos + `press('#search-input', 'Enter')` (**CORREGIDO**)
- BUG-E2E-014: Notes person-detail — placeholder `<tr>` engaña a `waitForSelector` → guard `apiGet + skip` + selector `.people-row` (**CORREGIDO**)
