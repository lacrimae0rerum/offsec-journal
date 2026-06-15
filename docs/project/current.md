# OffSec Journal — Estado operativo

> Actualizado: 2026-06-15. Admin UI completada (D4/F11). No hay sesión Alfred activa.

---

## Estado general

| Dimensión | Estado |
|---|---|
| Tests | 200 verdes (integración; sin E2E browser) |
| Contenedor dev | `127.0.0.1:8001` (Docker) / `127.0.0.1:8000` (local) |
| Deploy prod | 0% activo — sin nginx/Authelia/systemd configurado |
| CI/CD | Inexistente |
| Sesión Alfred | No inicializada (sin `alfred-dev-state.json`) |
| Kanban | No existe (`docs/project/kanban/` ausente) |
| Working tree | Cambios significativos SIN commitear desde 2026-06-08 |

---

## Working tree sin commitear

Todo el trabajo del sprint del 2026-06-08 está en el working tree, no en git:

- **D4/F11 completado (2026-06-15):** Admin UI — página `/admin` con gestión de usuarios y auth-events paginados; +12 tests (200 total)
- **D3 implementado:** filtros de búsqueda tipo/fechas/tags (backend+frontend, +10 tests)
- **Nivel 0 completado:** limpieza datos, XSS en prod, docs sincronizadas, +2 tests, higiene git
- **D1-D5 decididas:** bifurcación Línea A (producto) / Línea B (chat-agente)

**Acción inmediata antes de cualquier trabajo nuevo:** commitear o al menos revisar con `git diff --stat`.

---

## Trabajo pendiente por prioridad

### Línea A — Producto (sin bloqueos)

| ID | Item | Effort |
|---|---|---|
| D3 UAT | Verificación visual de filtros de búsqueda en navegador (pendiente de siempre) | — |
| P1 ROAD | 20 skill descriptions reales (TODO placeholders) | variable |
| P3 ROAD | `estimated_hours` — usar o eliminar del modelo | 30min |
| P5 ROAD | UI para unarchive (botón o journal explícito) | 1h |
| F1 | UI para `office_*` (3 kinds sin frontend) | ~3h |
| F2 | Skills matrix header dinámico | 1h |
| F3 | Buscador de clientes sin handler | 30min |
| F5 | Badge `pending` del journal dinámico | 15min |
| F6 | DRY `_renderNprSkillRows` / `_renderReqSkillRows` | 1h |
| F7 | `_SKILL_CATALOG` derivado de `DATA.skills` | 30min |
| F8 | Validación frontend `start <= end` | 20min |
| F9 | Fix search highlight con `&` espurio | 20min |
| F10 | Rate limit separado para `applyJournal` | 20min |
| F12 | Confirm modal en lugar de `confirm()` nativo | 30min |

### Línea B — Chat-agente (bloqueada)

| ID | Item | Bloqueado por |
|---|---|---|
| D1 | Spike: chat-agente LLM sobre `/api/*` | API key / proveedor sin decidir |

### Nivel 3 — Prod readiness (más adelante)

P1 (backup), P2 (Authelia endpoint migration), P4 (retention auth_event),
P8 (CI/CD), P9 (SSH hardening) — ver ROADMAP §7.

---

## Qué falta para trabajar con seguridad

1. **Commitear el working tree** — todo el trabajo desde 2026-06-08 (D3, Nivel 0, Admin UI) lleva sin commitear. Riesgo de pérdida.
2. **Crear kanban** — sin `docs/project/kanban/` Alfred no puede dar seguimiento fino.
3. **D3 UAT** — los filtros de búsqueda fueron implementados pero nunca verificados en navegador.

---

## Siguiente comando recomendado

Para la siguiente feature (oficinas sin frontend, o UAT de D3):

```
/alfred-dev:feature UI para office_* (3 kinds sin frontend)
```

Si quieres commitear todo lo acumulado primero:

```
/alfred-dev:quick commitear working tree completo (D3 + Nivel 0 + Admin UI)
```

Si quieres un resumen de tareas y kanban antes de decidir:

```
/alfred-dev:progress
```
