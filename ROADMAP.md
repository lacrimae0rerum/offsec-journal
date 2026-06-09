# OffSec Journal — Roadmap & Status

> **Documento vivo.** Marca con `[x]` lo cerrado, añade fecha+commit cuando aplique.

---

## 1. Cuadro de mando

| Capa | Cobertura | Estado |
|---|---|---|
| Backend (15 routers, 22 kinds) | 95% | Sólido — validación cross-entity en 14 kinds, rate limit en 3 mutadores, audit con 9 eventos |
| Frontend (11 páginas, 16 modales) | 78% | 9/11 páginas dinámicas. `chat` 100% mock, `search` aside **funcional** (D3: tipo/fechas/tags), sin UI admin |
| Tests | 188 verdes | Integración + rate-limit 429 (N0.5) + filtros de search (D3). **Sin E2E browser** |
| Documentación | 85% vigente | Drift de cifras corregido (2026-06-07); congelados marcados como históricos; CHANGELOG + mapa de proyecto añadidos. Pendiente: ADRs y guía de usuario |
| Deploy | 0% activo | Pendiente de configurar (nginx + Authelia + systemd) |

## 2. Pivotes vs visión original

- ❌ **LLM chat con Ollama 8B + tool-loop streaming** (era V1 obligatorio) — cero código, página `chat` solo mock
- ❌ **Next.js 14 + shadcn + Recharts** — pivote a HTML/CSS/JS estático
- ❌ **Docker Compose** — pivote a systemd nativo
- ✅ **Multi-tenant + Authelia + audit log** — añadidos al alcance original

---

## 3. Decisiones estratégicas

> **✅ RESUELTAS (2026-06-08).**
> El trabajo se bifurca en **Línea A** (producto actual: D3/D4/D5) y **Línea B** (chat con agente: D1).

- [x] **D1. ¿LLM chat sigue en el roadmap?** → **Pivote (Línea B):** no Ollama. Conectar `page-chat`
  a un agente respaldado por un proveedor LLM (vía API key). Tiene incógnitas técnicas → **spike**
  antes de implementar. El `page-chat` mock se conserva como base.

- [x] **D2. ¿Next.js volverá o V1 estático es definitivo?** → **Estático ahora, Next.js más adelante.**
  Sin migración inmediata; planificar a futuro. Prompt original ya archivado como histórico-pivote.

- [x] **D3. ¿`page-search` aside se implementa o elimina?** → **IMPLEMENTADO** (Línea A, 2026-06-08, sin commit):
  `/api/search` extendido con query params `types`/`date_from`/`date_to`/`tags` (team-scope intacto, sin inyección);
  aside wireado (checkboxes tipo, rango fechas, tags togglables, limpiar). skills/journal/orden sin backend → deshabilitados.
  +10 tests (188 total), ruff + sintaxis JS (bun) verdes. **Pendiente:** `/alfred-dev:verify` (UAT en navegador).

- [x] **D4. ¿Sección admin tendrá UI o queda CLI-only?** → **Construir la UI** (Línea A): página `/admin`
  con users + auth-events; wraps de `api.js` ya existen. Candidato a `/alfred-dev:feature` (~6h).

- [x] **D5. Pendientes vivos de diseño:** (Línea A, salvo P10)
  - [ ] **P1** rellenar 20 skill descriptions reales (actualmente `"TODO: operator-defined"`)
  - [ ] **P3** `estimated_hours` huérfano sin uso — usar para coverage o eliminar del modelo
  - [ ] **P5** unarchive UI — añadir botón explícito o usar `*_archive {archived:false}` por journal
  - [ ] **P10** el agente consulta `/api/skills` runtime → ahora pertenece a la **Línea B** (chat con agente)

---

## 4. Nivel 0 — Higiene inmediata

> **✅ COMPLETADO (2026-06-08).** Los 7 items (N0.1-N0.7) cerrados; cambios en el working tree sin commitear.
> Effort total estimado: ~2h. Limpia deuda visible antes de seguir.

- [x] **N0.1 Limpiar entries de prueba en producción** — `data/offsec/people.yaml` y `projects.yaml` _(2026-06-08, sin commit)_
  - Borradas 9 personas de prueba (`alex`, `e2etest`, `uitest1`, `xsstest`, `verifyfinal`, `toasttest`/`2`/`3`, `qa_xss_test`) incluidos los 2 payloads XSS; conservado solo `fer` ✅
  - Borrados 3 proyectos de prueba (`PT-2026-UI2`, `PT-2026-BTN1`, `QA-TEST-PROJECT-001`); conservados `CTI` y `Seur CTH` ✅
  - Verificado: sin payloads XSS en la fuente operativa, sin referencias en cascada (assignments/availability solo tienen `fer`), `sync` + 178 tests verdes
  - Nota: el payload XSS persiste en el audit log `data/offsec/journal.yaml` (histórico) → ver backlog §9
  - **Severidad:** alta operacional — XSS payload almacenado aunque sea archived
  - Effort: 30min

- [x] **N0.2 `make up` con `--no-proxy-headers`** _(2026-06-08, sin commit)_
  - Flag añadido al target `up` del `Makefile` ✅
  - Trampa para futuros deploys que copien el Makefile
  - Effort: 5min

- [x] **N0.3 Actualizar cifras de docs** _(2026-06-07)_
  - Corregidas cifras de tests desactualizadas en la documentación ✅
  - Añadida la fila del rate limiter al stack del README ✅
  - Effort: 15min

- [x] **N0.4 `.gitignore` ampliado** _(2026-06-08, sin commit)_
  - Añadidos `data/.backup-*/`, `data/**/*.yaml.bak`, `data/**/*.bak` y `.venv-mac/` ✅
  - Hoy estos contaminan `git status`
  - Effort: 5min

- [x] **N0.5 Tests de rate limit + reactivación de `_h_assign`** _(2026-06-08, sin commit)_
  - Nuevo `tests/test_rate_limit_and_reactivation.py` (2 tests, ambos verdes):
    - `tenant_writes` 60→61 = HTTP 429 con header `Retry-After` en POST `/api/journal` ✅
    - reactivación de assignment archivado en mismo `(person, project, start)` (1 row, en sitio, no duplicado) ✅
  - Suite total: 176 → **178 tests**
  - Effort: 30min

- [x] **N0.6 Quick wins UX del backlog del audit** _(2026-06-08, sin commit)_
  - [x] Pluralización "1 resultados" → "1 resultado" en `runSearch` (`web/app.js`) ✅
  - [x] `runSearch` skip si `q === ''` (no sobreescribir placeholder al montar `/search`) ✅
  - [x] Toast obsoleto "Configura la API key (panel ⚙)" (líneas 1466 y 1694) → mensaje "Sin conexión con el servidor" ✅
  - [x] `data.js scheduleWeeks` → vaciado a `[]` ✅
  - [x] Crear proyecto sin código → ya disparaba toast claro ("Código, Cliente y Tipo son obligatorios") ✅ (ya cubierto)
  - Nota: cambios JS no validados con linter (sin `node` en el entorno); son ediciones quirúrgicas
  - Effort: 30min total

- [x] **N0.7 Decidir destino del flag `DEV_ALLOW_LAN`** _(2026-06-08)_
  - **Decisión: conservar** (escape hatch explícito y documentado). Se deja en el working tree para commitear; no se descarta ni stashea
  - `api/config.py` y `api/main.py` sin tocar (ya tenían el cambio)
  - Effort: 5min

---

## 5. Nivel 1 — Espera de decisiones estratégicas

> Bloqueado hasta resolver D1-D5. Ver sección 3.

---

## 6. Nivel 2 — Features para cerrar huecos cross-stack

> Ejecutables tras N0 y D1-D5. Effort estimado 2-4h cada uno salvo nota.

- [ ] **F1. UI para `office_*` (3 kinds sin frontend)**
  - Backend: `office_create`, `office_update`, `office_archive` listos en `api/core/journal.py`
  - Frontend: ningún modal, ningún botón
  - Acción: añadir página o sección admin de oficinas
  - Effort: ~3h

- [ ] **F2. Skills matrix header dinámico**
  - `web/index.html:367-376` tiene 10 IDs de skill **hardcoded**
  - Si admin archiva o crea skill via `ncs-submit`, la matriz no refleja cambios
  - Acción: render dinámico de columnas desde `DATA.skills.filter(!archived)`
  - Effort: 1h

- [ ] **F3. Buscador izquierda de `page-clients` sin handler**
  - `web/index.html:301` input `placeholder="Buscar cliente..."` sin listener
  - Acción: wire substring filter equivalente al de People
  - Effort: 30min

- [ ] **F4. Counts dinámicos en search filters**
  - `web/index.html:503-505` muestra `personas (2) proyectos (1) notas (1)` hardcoded
  - Acción: calcular desde `res.people.length` etc o eliminar si D3=eliminar
  - Effort: 30min (solo si D3=mantener)

- [ ] **F5. Badge `pending (1)` del journal**
  - `web/index.html:413` count estático en pestaña pending
  - Acción: calcular desde `DATA.journal.filter(j => j.status === 'pending').length`
  - Effort: 15min

- [ ] **F6. DRY skill rows**
  - `_renderNprSkillRows` (~1712) y `_renderReqSkillRows` (~2152) son ~95% idénticos
  - Drift: uno usa `addEventListener`, otro `onclick` inline
  - Acción: factoría `makeSkillRowsRenderer({prefix, container, stateKey})`
  - Effort: 1h

- [ ] **F7. `_SKILL_CATALOG` derivado de `DATA.skills`**
  - Hardcoded duplicado en `web/app.js:~1801` y `~1953`
  - Si admin crea skill via `ncs-submit`, los selects no la ven
  - Acción: derivar de `DATA.skills.filter(s => !s.archived).map(s => s.id)`
  - Effort: 30min

- [ ] **F8. Validación frontend `start <= end`**
  - `wireProposeAssignModal`, `wireNewProjectModal`, `wireNewAvailModal`
  - Hoy: backend rechaza pero el toast es feo
  - Acción: validar antes de POST con `_toast(..., 'warn')`
  - Effort: 20min

- [ ] **F9. Search highlight `&` espurio**
  - `runSearch` escapa `q` con HTML antes del regex → query con `&` matchea `&amp;` en cualquier body
  - Acción: aplicar `_escapeRegex(q)` sobre `safe` (HTML-escaped body) sin escapar `q` HTML primero
  - Effort: 20min

- [ ] **F10. Rate limit separado para `applyJournal`**
  - Hoy `tenant_writes` (60/min) cubre create + apply + reject
  - Si tienes 70 entries pending y aplicas en bucle, el 61º falla
  - Acción: subir a 120 o bucket separado para apply
  - Effort: 20min

- [ ] **F11. Admin UI** _(solo si D4=sí)_
  - Página nueva `/admin` con tablas de `users` y `auth-events`
  - Wraps de `api.js` ya existen (líneas 94-101); falta `web/index.html` + handlers
  - Effort: ~6h

- [ ] **F12. Confirm modal en lugar de `confirm()` nativo**
  - `wireContactModal` (~1755) usa `confirm()` bloqueante
  - Inconsistente con resto del proyecto que usa `_toast` + modales
  - Effort: 30min

---

## 7. Nivel 3 — Prod readiness (antes de desplegar)

- [ ] **P1. Backup off-site** (p. ej. rclone)
- [ ] **P2. Migrar endpoint Authelia** `/api/verify` → `/api/authz/forward-auth` (deprecación)
- [ ] **P3. Cert separado por dominio** (no SAN multi-dominio compartido)
- [ ] **P4. Retention policy `auth_event`** (~300k rows/año, hoy infinito)
- [ ] **P5. Checklist manual** actualizado a la UI multi-tenant post-Authelia
- [ ] **P6. Log shipping a SIEM externo**
- [ ] **P7. Monitoring/alertas systemd**
- [ ] **P8. CI/CD** (hoy 0) — pipeline mínimo con tests + lint
- [ ] **P9. SSH hardening** del servidor de despliegue

---

## 8. Bugs abiertos

> Reportados por usuario o agentes en sesiones recientes que no estén ya cerrados en el commit `4d3a779`. Añadir aquí cuando aparezcan.

| ID | Severidad | Resumen | Reportado | Estado |
|---|---|---|---|---|
| _ninguno por ahora_ | | | | |

---

## 9. Backlog del audit (MEDIOS/BAJOS sin escalar a Nivel 0-2)

> Hallazgos de las 5 auditorías del 27-abr que no caen en niveles operativos. Revisar periódicamente — si alguno se vuelve urgente, promover a Nivel 0.

- [ ] DRY `H = _escapeHtml` repetido por función → extraer al top de `web/app.js`
- [ ] `paintIdentity` no normaliza `dataset.team` a string — edge defensive
- [ ] `data/offsec/journal.yaml` con 1942 líneas de histórico mezclado (tests + reales). Decidir cleanup o aceptar como audit log
- [ ] Sin tests E2E browser (Playwright/Cypress) — solo integración FastAPI TestClient
- [ ] `tests/test_rollback.py::test_backup_file_exists_after_apply` no covers el caso "sync() falla y deja `.bak` corrupto"
- [ ] `make up` con `--reload` (dev) — drift dev/prod implícito
- [ ] `auth_event` sin paginación de UI (CLI sí, pero si se hace UI admin, paginar)

---

## 10. Histórico

| Fecha | Evento | Commit |
|---|---|---|
| 2026-06-08 | D3 implementado: filtros de búsqueda (tipo/fechas/tags) backend+frontend, +10 tests (188) | sin commit |
| 2026-06-08 | D1-D5 resueltas; bifurcación Línea A (producto) / Línea B (chat con agente) | sin commit |
| 2026-06-08 | Nivel 0 completado (N0.1-N0.7): limpieza datos+XSS, docs sincronizadas, +2 tests (178), higiene git | sin commit |
| 2026-04-27 | Sprint UX+seguridad: 8 ALTOS + audit + QA | `4d3a779` |
| 2026-04-24 | Migración multi-tenant completada (176 tests verdes) | `54cbb12` |
| 2026-04-24 | CLI offsec + admin endpoints + frontend | `6cda22a` |
| 2026-04-24 | Refactor team-scoped queries + journal | `3218a66` |
| 2026-04-19 | Authelia middleware + audit log + rate limiter | `30a7798` |

---

## Cómo trabajar con este documento

- **Marca `[x]` y añade fecha + commit** cuando cierres un item: `- [x] N0.1 Limpiar entries de prueba (2026-04-29, abc1234)`
- **Si descubres un bug, añádelo a §8** con severidad y reportador
- **Si surge una decisión estratégica nueva**, añádela a §3 con número (D6, D7…)
- **Si un item del backlog se vuelve urgente**, promuévelo a Nivel 0-2
- **Mantén el cuadro de mando (§1) actualizado** tras cambios grandes
