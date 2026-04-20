# Tests manuales — estado actual

Checklist para validar a mano el frontend + integración con backend. Numerados para que puedas decir "falla el 37" en lugar de describir.

Leyenda: ✅ esperado · ⚠️ comportamiento conocido (no es bug) · 🟢 online (backend conectado) · ⚫ offline (sin API key) · 🔴 fallo si sucede algo distinto

---

## Setup

**1.** `make install` en raíz → se genera `.env` con `API_KEY` → ✅ aparece el valor en consola.
**2.** `make up` en una terminal → uvicorn arranca en `:8000`, sirve api + frontend.
**3.** Abrir http://localhost:8000/ en Chrome/Firefox → la app carga y **el badge se pone verde solo** (auto-bootstrap via `/api/bootstrap`).
**4.** F12 → Console no muestra errores rojos. F12 → Network, `/api/bootstrap` devuelve 200 con `{api_key, api_base}`.

---

## Arranque y estado base

**5.** Tras cargar, el badge superior derecho dice **"Online · localhost:8000"** (verde con glow) automáticamente. Si no hay bootstrap disponible, mostrará "Offline · pega tu API key en ⚙". ✅
**6.** La pestaña activa es **Overview**. ✅
**7.** La sidebar muestra 10 items: Overview, People, Projects, Clients, Schedule, Skills, Map, Journal, Chat, Search. ✅
**8.** En la sidebar, "Overview" está resaltado en azul con borde izquierdo. ✅
**9.** Arriba de la sidebar hay un recuadro "LOGO" con un texto placeholder al lado (por defecto "MSSP" — editable en `index.html`). ✅

---

## Navegación global

Clicar cada item del sidebar en orden y verificar que carga la página correspondiente:

**10.** Click en **People** → título "People", tabla con 6 filas. ✅
**11.** Click en **Projects** → título "Projects", tabs "Kanban / Tabla", kanban con 3 columnas. ✅
**12.** Click en **Clients** → lista con 3 clientes + detalle "Cliente Alfa" abierto. ✅
**13.** Click en **Schedule** → título "Schedule", heatmap 6 personas × 4 semanas. ✅
**14.** Click en **Skills** → matriz 6×10 niveles. ✅
**15.** Click en **Map** → mapa con 3 markers (Madrid 3, Barcelona 2, Lisboa 1). ✅
**16.** Click en **Journal** → tabs Pending/Applied/Rejected, al menos 1 entry. ✅
**17.** Click en **Chat** → 3 flows mockeados + panel lateral de tool calls. ✅
**18.** Click en **Search** → facets a la izquierda + 4 resultados con "cloud" highlight. ✅
**19.** Click en **Overview** de vuelta → la pestaña original carga sin reset. ✅

---

## Overview

**20.** Se ven 5 KPIs: Personas 6, Proyectos activos 5, Pipeline 3, Coherence warnings **2** (en ámbar), Carga media 78%. ✅
**21.** El heatmap muestra 6 personas × 4 semanas (1M activo por defecto). ✅
**22.** Los botones de rango **1S 2S 3S 1M 2M 3M 4M 5M 6M** están todos visibles sin desbordar el card. ✅
**23.** Click en **1S** → 1 columna visible, la altura de las celdas se mantiene igual (no se estira). ✅
**24.** Click en **6M** → 26 columnas visibles, celdas siguen dentro del card, el número "%" se ve legible. ✅
**25.** Los colores del heatmap incluyen: gris (0%), azul claro (1-20%), azul medio (40-60%), azul fuerte (60-80%), **ámbar** (80-100%), **rojo** (>100%). ✅
**26.** Hover sobre una celda → se agranda ligeramente (scale 1.12). ✅
**27.** Panel "Top skill gaps": 3 skills con badges coloreados. ✅
**28.** Panel "Coherence warnings (2)": 2 cajas ámbar con rule + detalle. ✅
**29.** Click en `tbd_03` dentro de coherence warnings → navega a Person Detail de tbd_03. ✅
**30.** Panel "Últimas entradas del journal": 3 entries con badges applied/pending. ✅

---

## People

**31.** Tabla muestra 6 filas: fer, santi, tbd_01, tbd_02, tbd_03, tbd_04. ✅
**32.** Badge de nivel: verde para senior sano (fer, santi), ámbar para `tbd_03 senior ⚠`, gris para resto. ✅
**33.** Fila `tbd_03` tiene un ⚠ en la última columna con tooltip "insufficient_skill_coverage". ✅
**34.** Filtros arriba: 3 dropdowns (oficinas, niveles, skills) — son decorativos, no filtran todavía. ⚠️
**35.** Click en fila **fer** → abre drawer lateral con radar, skills, assignments, notas. ✅
**36.** Drawer muestra nombre "Alex P.", ID `fer`, metadata "Madrid · senior · FTE 1.0 · desde 2019-03-01". ✅
**37.** Click en botón ✕ del drawer → cierra. ✅
**38.** Click fuera del drawer → cierra. ✅
**39.** Reabrir drawer y click en "→ Ver página completa" → cierra drawer y navega a Person Detail. ✅
**40.** Botón "+ Nueva persona" arriba a la derecha → abre modal `new-person-modal`. ✅

---

## Person Detail (`/people/fer`)

**41.** Breadcrumb "← People /people/fer" visible arriba. ✅
**42.** Click en "← People" → vuelve a People. ✅
**43.** Radar SVG con 6 ejes (web, ad, osint, priv, report, cloud) dibujado. ✅
**44.** Tabla "Skills detalle" con 7 filas (las skills de fer). ✅
**45.** Click en una fila de skill (ej. `hacking_cloud`) → abre modal `skill-modal` en modo edit con los valores prefills. ✅
**46.** Al final de la tabla hay botones **"+ Añadir skill"** y **"Archivar persona"**. ✅
**47.** Click en "+ Añadir skill" → modal en modo add, dropdown con las 20 skills del catálogo. ✅
**48.** Tabla "Assignments activos" con 2 filas (PT-2026-012, CTI-2026-003). ✅
**49.** Sección "Coherence": "✓ senior coherente…" (fer pasa). ✅
**50.** Sección "Disponibilidad": 2 filas (PTO + training). ✅
**51.** Botón "+ PTO / training" → abre modal `new-avail-modal`. ✅
**52.** Sección "Notas": 3 notas con separador `ts | author | tags`. ✅
**53.** 🟢 Textarea "Añadir nota" + input "tags: a,b,c" + botón → `POST /api/notes` → notas se re-renderizan con la nueva arriba. ✅
**53b.** Botón "Editar persona" en header → abre `edit-person-modal` con todos los campos prefills. ✅
**53c.** Modal edit-persona: al cambiar solo nivel global y guardar → `_diffPayload` envía únicamente `global_level` (diff automático). ✅
**53d.** Guardar sin cambios → alert "No hay cambios que guardar". ✅

---

## Projects

**54.** 2 tabs: **Kanban** (activo) y **Tabla**. ✅
**55.** Kanban con 3 columnas: **pipeline** (3 cards), **active** (5 cards), **closed** (placeholder "Sin proyectos cerrados"). ✅
**56.** Cada card muestra código, tipo, cliente, ventana, cobertura con badge coloreado. ✅
**57.** Click en **Tabla** → vista kanban desaparece, aparece tabla con 8 filas. ✅
**58.** Click de vuelta en **Kanban** → reaparece. ✅
**59.** Botón "+ Nuevo proyecto" → abre modal `new-project-modal`. ✅
**60.** Click en un card/row → navega a Project Detail. ✅

---

## Project Detail (`/projects/PT-2026-018`)

**61.** Breadcrumb "← Projects /projects/PT-2026-018". ✅
**62.** Tabla "Required skills vs equipo" con 5 filas; `hacking_cloud` con badge rojo "-1 nivel". ✅
**63.** Barra de cobertura roja al 40% + badge "40%". ✅
**64.** Card "Assignments actuales" con placeholder "Sin assignments (proyecto en pipeline)". ✅
**65.** Botón "+ Proponer assignment" → abre modal `propose-assign-modal`. ✅
**66.** Botón "Archivar proyecto" (rojo) → abre modal `archive-modal`. ✅
**67.** Card "Timeline" con barra ámbar W19-W23. ✅
**68.** 🟢 Card "Notas" — carga live desde `/api/notes?entity_type=project&entity_id=...`; submit crea, re-renderiza, newest-first. ✅
**68b.** Botón "Editar proyecto" en header → abre `edit-project-modal` con cliente, tipo, fechas, horas, status. ✅
**68c.** Dentro del modal, botón "Editar required skills →" cierra el actual y abre `req-skills-modal`. ✅
**68d.** Modal req-skills: "+ Añadir skill requerida" añade fila; ✕ por fila la elimina. ✅
**68e.** Guardar required skills → POST con `required_skills` como array completo (deduplicado por skill_id). ✅

---

## Clients

**69.** Sidebar izquierda: 3 clientes (Alfa activo, Gamma, Epsilon) + botón "+ Nuevo cliente" abajo. ✅
**70.** Click en otro cliente de la lista → detalle derecho cambia, fila activa se resalta. ✅
**71.** En Cliente Alfa: descripción, 2 proyectos en tabla, 2 contactos con avatar iniciales JM/LR. ✅
**72.** Click en un contacto → abre modal `contact-modal` en modo edit con valores prefills. ✅
**73.** Botón "+ Contacto" arriba del card de contactos → abre modal en modo add. ✅
**74.** Botón "Archivar" en card de contactos → abre modal `archive-modal`. ✅
**74b.** Botón "Editar" junto al nombre del cliente → abre `edit-client-modal` con campos prefills. ✅
**74c.** Al cambiar un cliente distinto en la sidebar → el detalle actualizado cargará con su propio id para editar. ✅
**75.** Card "Placeholders futuros" con 3 bloques rayados (SLA, Facturación, NPS). ✅
**76.** Card "Notas" con textarea para añadir. ✅
**77.** Botón "+ Nuevo cliente" (tanto el de la sidebar como el de arriba) → abre `new-client-modal`. ✅
**77b.** 🟢 Card "Notas" del cliente: carga live `/api/notes?entity_type=client&entity_id=...`; submit persiste en `notes/clients/{id}.md`. ✅

---

## Schedule

**78.** Heatmap 6 personas × 4 semanas (W15-W18). ✅
**79.** La celda **tbd_02 W16 110%** aparece en **rojo** con "⚠". ✅
**80.** Hover sobre una celda → aparece popover con Total + tabla proyecto/%/rol/hrs. ✅
**81.** Popover de una celda en la fila superior aparece **debajo** (flip) — no tapa el scroll. ✅
**82.** Popover no queda cortado por el borde del card (usa `position:fixed`). ✅
**83.** Leyenda de colores abajo muestra los 7 tramos. ✅
**84.** Cambiar input de inicio a `2026-W20` → click "Aplicar" → el heatmap recarga con nuevas columnas; contador "· N semanas" se actualiza. ✅
**84b.** Rango de 8 semanas (ej. W15→W22) → grid muestra 8 columnas, contador "· 8 semanas". ✅

---

## Skills

**85.** Tab "Matriz de niveles" (activa) muestra tabla 6×10 con celdas coloreadas por nivel. ✅
**86.** Click en "Skill gap (pipeline)" → matriz desaparece, aparecen 4 barras horizontales. ✅
**87.** Cada barra tiene fill azul + texto "have/need" a la derecha + badge de déficit. ✅
**88.** Click en "Matriz de niveles" → vuelve. ✅
**88b.** Botón "+ Nueva skill" en header → abre modal `new-catalog-skill-modal`. ✅
**88c.** Modal nueva skill: ID debe ser snake_case (validación `[a-z][a-z0-9_]*`), label obligatorio. ✅
**88d.** En la cabecera de la matriz, click en "✕" junto a una skill → confirm → entry `skill_catalog_archive` pending. ✅
**88e.** Click en "✎" junto a una skill → abre `edit-skill-label-modal` con label/desc editables. ✅
**88f.** Modal edit-skill-label: si ambos quedan vacíos → alert "Nada que cambiar". ✅

---

## Map

**89.** Se ve una cuadrícula azul (grid small + grid large) visible sobre el fondo negro + una silueta rayada simulando península + 4 labels de latitud arriba. ✅
**90.** 3 markers circulares con números (3, 2, 1). ✅
**91.** Click en Madrid (marker "3") → popover con "Madrid · 3 persona(s)" y 3 IDs. ✅
**92.** Click en otra zona → popover se cierra. ✅
**93.** Link "→ Ver en People" dentro del popover → navega a People. ✅

---

## Journal

**93.** Por defecto tab "Pending" activo, contador "1" en badge ámbar. ✅
**94.** Entry pending visible: `skill_update` + "Subir tbd_01.hacking_web de L3 → L4". ✅
**95.** Entry tiene botones **"✓ Aplicar"** y **"✗ Rechazar"**. ✅
**96.** Tabs "Applied" y "Rejected" clicables. ✅
**97.** En "Applied" aparecen 2 entries (santi → PT-2026-014 y fer: PTO 21-25 abr). ✅
**98.** Las entries applied/rejected **no** tienen botones de acción. ✅
**99.** Click en **"✗ Rechazar"** sin reason → abre modal `reject-modal` con el subject prefills. ✅
**100.** Click en "Confirmar rechazo" sin llenar textarea → alerta "La razón es obligatoria". ⚫ ✅
**101.** Click en ✕ del modal → cierra sin hacer nada. ✅

---

## Chat

**102.** 3 flows mockeados visibles (skill_gap, find_people, propose_assignment). ✅
**103.** Panel derecho "Tool calls" con 3 tool cards. ✅
**104.** Cursor parpadeante azul al final del último assistant msg. ✅
**105.** Input de texto abajo habilitado; botón "Enviar" no funcional (falta LLM). ⚠️

---

## Search

**106.** Input pre-rellenado con "hacking cloud". ✅
**107.** Sidebar facets izquierda: 5 tipos checkbox, date range, tags chips, orden dropdown. ✅
**108.** Línea "4 resultados · 38 ms · índice SQLite FTS5". ✅
**109.** 3 grupos: Personas (2), Proyectos (1), Notas (1). ✅
**110.** "cloud" aparece con highlight azul en cada resultado. ✅

---

## Tweaks panel

**111.** Click en el icono ⚙ abajo-derecha → panel de tweaks abierto, icono desaparece. ✅
**112.** 2 inputs: "API Base URL" (default `http://localhost:8000`) y "API Key" (vacío). ✅
**113.** Botones "Guardar + probar" y "✕ limpiar". ✅
**114.** Selectores "Sidebar" (Expandida/Mini) y "Schedule" (Hover/Click). ✅
**115.** Cambiar Sidebar a "Mini" → sidebar se encoge a iconos solamente. ✅
**116.** Cambiar Schedule a "Click" → hover deja de abrir popover, hay que clickar. ✅
**117.** Click en "Cerrar" → panel se oculta, icono ⚙ reaparece. ✅

---

## Modo ONLINE 🟢

**118.** **Con `make up` solo**: abrir http://localhost:8000/ — el badge pasa a verde sin tocar nada (auto-bootstrap via `/api/bootstrap`). ✅
**119.** Si abres Tweaks, los campos "API Base URL" y "API Key" ya están rellenos automáticamente. ✅
**120.** Ir a Journal → entries vienen del backend (al menos 3 desde el seed). ✅
**121.** Entries de live tienen IDs ULID reales (26 chars), distintos de los mock. ✅
**121b.** Tras "Guardar + probar", **todas** las páginas se re-renderizan con datos reales (refreshAll): counts de KPIs, tabla de people, kanban de projects, sidebar de clients, matriz de skills. ✅
**121c.** Overview: la columna "Coherence warnings" muestra el count real (suele ser 3 con seed, no 2). ✅
**121d.** Overview heatmap: las celdas reflejan las assignments reales en el rango actual. ✅
**121e.** People: columna "Carga sem." es la suma real de % de assignments de cada persona. ✅
**121f.** Projects kanban: las badges de cobertura cambian a los valores computados (no los hardcoded 40%/85%/etc). ✅
**121g.** Skills: la cabecera de la matriz muestra IDs reales del catálogo (no las abreviaturas `web/ad/osint...`). ✅
**121h.** Map: marker de Madrid muestra el count y los IDs reales de `/api/geo` (no el mock "tbd_05"). ✅
**121i.** Search: escribir cualquier término dispara `/api/search` con 220ms de debounce; resultados se reemplazan sin recargar página. ✅
**121j.** Tras aplicar/rechazar/crear cualquier entry, `refreshAll()` corre y se ve el cambio en todas las páginas (journal, overview, detalles). ✅

---

## End-to-end (🟢 online)

**122.** **Crear cliente**: Clients → "+ Nuevo cliente" → id "test_client", nombre "Test SA", sector "Tech". "Crear entry" → modal cierra. ✅
**123.** Ir a Journal → aparece nueva entry **pending** con kind `client_create`, proposer `human`. ✅
**124.** Click "✓ Aplicar" → entry pasa a applied (reload). ✅
**125.** Verificar en terminal: `ls data/clients.yaml.bak` existe + `grep test_client data/clients.yaml` devuelve la línea. ✅

**126.** **Archivar un proyecto**: navegar a Project Detail (click en card del kanban) → botón "Archivar proyecto" → "Crear entry de archivo". ✅
**127.** Journal → entry `project_archive` pending → Aplicar. ✅
**128.** Verificar en terminal: `grep -A3 'code: PT-2026-018' data/projects.yaml | grep archived: true` debe devolver la línea. ✅

**129.** **Proponer assignment**: Project Detail → "+ Proponer assignment" → elegir persona, %, fechas, role → Crear. ✅
**130.** Journal → entry `assign` pending → Aplicar. ✅
**131.** `GET /api/projects/:code` via `curl -H "X-API-Key: $KEY"` muestra la assignment nueva. ✅

**132.** **Editar skill**: Person Detail → click en fila `hacking_cloud` → cambiar level a 3 → Crear entry. ✅
**133.** Journal → `skill_update` pending → Aplicar. ✅
**134.** Re-navegar a la Person Detail → la skill debería mostrar L3. ⚠️ (pendiente: wire-up que haga refetch tras apply).

**135.** **Reject con reason**: crear cualquier entry, en Journal click "✗ Rechazar" → escribir "test reason" → Confirmar. ✅
**136.** Entry desaparece de pending, aparece en tab "Rejected" con reason visible. ✅

**137.** **Contact add**: Client detail de alfa → "+ Contacto" → nombre "Alice Test", role "CFO", email. Crear entry → Aplicar. ✅
**138.** `curl /api/clients/alfa` con API key debería listar 3 contactos (los 2 originales + Alice). ✅

---

## Rollback y errores

**139.** 🟢 Crear entry con payload duplicado (ej. `assign` a una persona que ya tiene esa asignación en la misma start date) → Aplicar → devuelve error, entry queda pending. ✅
**140.** Verificar `data/assignments.yaml.bak` existe; `data/assignments.yaml` no cambió. ✅
**141.** 🟢 Reject sin reason → backend devuelve 400 → frontend muestra alert. ✅
**142.** ⚫ Con API Key vacía, click en cualquier botón de modal → alert "Configura la API key…". ✅
**143.** 🔴 Borrar `.env`, reiniciar `make up` → badge ya no llega a "Online" (la key cambia). ✅

---

## Regresión visual

**144.** Cambiar el navegador a 1280×800 → sidebar de 260px, todo el contenido entra. ✅
**145.** Cambiar a 900×600 → sidebar se encoge a 64px mini automáticamente (media query). ✅
**146.** En mini-mode, los iconos siguen visibles, labels desaparecen. ✅
**147.** Badge de status nunca tapa el contenido principal. ✅
**148.** Scroll en una tabla larga (ej. Skills matrix con muchas columnas) no rompe el layout. ✅

---

## Persistencia

**149.** Configurar API key → recargar página (F5) → badge vuelve a "Online" sin pedir config otra vez (localStorage). ✅
**150.** Click "✕ limpiar" en Tweaks → vuelve a "Offline". ✅

---

## Límites conocidos (no son bugs)

- ⚠️ Filtros de People no filtran (son decorativos)
- ⚠️ Input del Chat no envía nada (LLM pendiente)
- ⚠️ Heatmap no hace resize recalculation al cambiar de tamaño de ventana

---

## Reporte

Si un test falla, anota:
- Número del test (ej. "falla el 42")
- Qué viste vs qué esperabas
- Captura de pantalla si es visual
- Consola del navegador (F12 → Console) si hay error JS
- Terminal de uvicorn si es 5xx

Con eso puedo arreglar un bug en ~1 turno por defecto.
