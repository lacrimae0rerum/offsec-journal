# Registro de bugs

Lista cronológica de problemas detectados durante desarrollo, QA manual o uso real. Cada bug tiene: ID, cuándo, qué pasó, cómo se reprodujo, fix aplicado, verificación.

Estados: 🟢 Fixed · 🟡 Workaround · 🔴 Open

---

## Bugs de arranque (2026-04-19)

### BUG-001 🟢 `python: not found` al correr `make install` en WSL
- **Síntoma:** `make install` → `/bin/sh: 1: python: not found`
- **Causa:** WSL/Ubuntu usa `python3`; el Makefile hardcodeaba `python`
- **Fix:** Makefile autodetecta con `command -v python3 || command -v python`
- **Verificación:** `make install` arranca en WSL sin overrides
- **Commit:** Makefile — `PYTHON ?= $(shell command -v python3 2>/dev/null || ...)`

### BUG-002 🟢 `externally-managed-environment` (PEP 668) en Ubuntu 24+
- **Síntoma:** `make install` → `error: externally-managed-environment` al hacer pip install
- **Causa:** Ubuntu 23.04+ bloquea pip a nivel sistema; obliga a usar venv
- **Fix:** Makefile crea `.venv/` automáticamente con `python3 -m venv` y todas las targets lo usan
- **Verificación:** `make install` crea `.venv/`, instala deps ahí, `.env` generado, sync corrido
- **Commit:** Makefile — targets `install`/`up`/`test`/`sync`/`reset`/`web` usan `VENV_PY`

### BUG-003 🟢 `.venv/bin/python: not found` al correr `make web`
- **Síntoma:** `make web` → `/bin/sh: 1: .venv/bin/python: not found`
- **Causa:** `cd web && $(PYTHON) ...` — la ruta relativa al venv se rompe tras el `cd`
- **Fix:** usar `python -m http.server 3000 --directory web` sin cambiar cwd
- **Verificación:** `make web` arranca desde la raíz, sirve `web/` en :3000
- **Commit:** Makefile — target `web`

---

## Bugs funcionales

### BUG-004 🟢 Schedule: los inputs de rango no recargan el heatmap
- **Síntoma:** cambiar los inputs `type="week"` en la página Schedule no afecta al heatmap; sigue mostrando W15–W18 fijo
- **Reproducción:** Schedule → cambiar input de inicio a `2026-W20` → no pasa nada
- **Causa:** `buildScheduleHeatmap()` usaba `DATA.scheduleWeeks` hardcodeado; los inputs y el botón "Aplicar" eran decorativos
- **Fix:** los inputs están cableados; el botón "Aplicar" calcula ISO weeks entre fechas y reconstruye el heatmap. Si online, hace `api.getHeatmap(start, end)`; si offline, usa la tabla seed con módulo
- **Verificación:** cambiar rango a 8 semanas → el heatmap muestra 8 columnas

### BUG-005 🟡 Skills catalog: no se podían crear ni archivar skills desde la UI
- **Síntoma:** la página Skills solo es lectura; el prompt original definía el catálogo como "cerrado a 20"
- **Reproducción:** Skills → no hay botones de acción
- **Causa:** decisión #3 original: solo editar `label_es`/`description`
- **Fix:** reabre el catálogo — añadidos journal kinds `skill_create` + `skill_archive`, handlers en `core/journal.py` con tests, modal `new-skill-modal` en UI, botón "+ Nueva skill" en header, botón "Archivar" por fila de matriz
- **Nota:** cambia el alcance del prompt original — el LLM deberá consultar `/api/skills` en runtime en vez de asumir las 20 fijas. Documentado en OPEN_QUESTIONS P10
- **Verificación:** tests nuevos `test_handler_skill_create` + `test_handler_skill_archive` verde

### BUG-007 🟢 Parser de notas: tags con guión rompen la regex
- **Síntoma:** `GET /api/notes?entity_type=person&entity_id=fer` devuelve sólo 2 notas cuando el markdown tiene 3+; la nota del medio (con `tags: cti, client-delta`) desaparece
- **Reproducción:** Person Detail de fer online → solo se ven 2 notas; `/api/search?q=cti` no encuentra la nota
- **Causa:** `NOTE_SEP_RE` usaba `tags:\s*(?P<tags>[^-]*)\s*---` — el character class `[^-]*` no deja pasar guiones, así que se cortaba antes del ` ---` final y la línea entera no se reconocía como separador. La nota siguiente se acumulaba como body de la anterior y se "perdía"
- **Fix:** cambiar a `tags:\s*(?P<tags>.*?)\s+---` con non-greedy y matcheo explícito del terminador; `\s+` entre delimitadores `|` para ser más tolerante con espacios
- **Verificación:** `_parse_markdown_notes(fer.md)` devuelve 5 notas incluyendo la de `client-delta`; test nuevo `test_parser_handles_hyphen_tags` verde

### BUG-006 🟢 Map: la cuadrícula de fondo no era visible sobre el negro
- **Síntoma:** en la página Map se ven los 3 markers pero el mapa de fondo no se distingue — parece un rectángulo negro con puntos
- **Reproducción:** abrir Map
- **Causa:** el SVG de grid tenía `opacity: 0.18` y `stroke-width: 0.5` — demasiado sutil sobre `#000`
- **Fix:** subida opacidad a `0.35`, grosor de líneas a `0.7`, añadidas líneas principales cada 200px más visibles, label de "Europa · red local" abajo a la derecha y un par de "landmarks" genéricos para dar contexto visual
- **Verificación:** test visual #89 reformulado en MANUAL_TESTS para exigir grid visible

<!-- Plantilla:

### BUG-NNN 🔴 Título corto
- **Síntoma:** qué pasa
- **Reproducción:** pasos exactos (referencia MANUAL_TESTS #NN si aplica)
- **Entorno:** navegador, modo online/offline, página activa
- **Consola/logs:** errores de F12 o del uvicorn
- **Causa:** root cause identificada
- **Fix:** qué se cambió y dónde
- **Verificación:** test que garantiza no-regresión

-->
