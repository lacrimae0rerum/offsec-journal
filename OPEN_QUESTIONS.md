# OPEN_QUESTIONS.md

Decisiones ya cerradas y preguntas abiertas. Vive junto al código para que no se pierdan en el chat.

---

## Decisiones cerradas

Todas acordadas con el operador principal el 2026-04-18 / 2026-04-19.

### 1. Apply de entries `human`: 2 clicks
Cuando tú creas un proyecto / availability / persona desde un modal del frontend, se crea entry `pending` en el journal igual que las propuestas del LLM. Hay que ir a `/journal` y pulsar apply. No hay atajo de 1 click.

**Rationale:** auditoría homogénea. El `/journal` es la única puerta a mutaciones estructurales, venga del LLM o de un humano.

### 2. Soft delete siempre
`archived: true` en el YAML. Hard delete no existe en la UI. Los filtros `list_*` excluyen archivados por defecto; pasar `?archived=true` los incluye.

**Rationale:** el YAML está versionado en git — si algo se borra de verdad, la recuperación requiere arqueología en el log. Soft delete mantiene FK integrity y permite unarchive.

### 3. Skill catalog: UI editable para labels + descriptions — **AMPLIADO 2026-04-19**
Inicialmente el catálogo era cerrado (las 20 skills del prompt). Ampliado para permitir crear y archivar skills desde la UI (journal `skill_catalog_create` + `skill_catalog_archive`). Labels/descriptions siguen editables vía `skill_label_update`.

**Rationale:** equipos reales añaden técnicas nuevas (ej. hacking_kubernetes) y jubilan otras. Forzar rebuild del código para ampliar el catálogo es fricción innecesaria.

**Impacto:** el LLM tendrá que consultar `/api/skills` en runtime en lugar de asumir las 20 fijas. Ver P10.

### 4. Notas append-only estricto
No hay edit ni delete de notas existentes. Cada nota es un bloque markdown con separador `--- <ts> | <author> | tags: <csv> ---`.

**Rationale:** audit trail. Una nota sobre un cliente o una persona que aparece y desaparece es peor que una nota equivocada — la equivocada se corrige con una nota nueva que la contradiga.

### 5. Journal: solo kinds tipados
El discriminator acepta 20 operaciones (`assign`, `unassign`, `availability`, `skill_update`, `person_create/update/archive`, `project_create/update/archive`, `client_create/update/archive`, `contact_add/update/remove`, `office_create/update/archive`, `skill_label_update`). No hay `otras_ops` freeform.

**Rationale:** cada kind tiene un handler con validación y rollback. Freeform requiere interpretación → pérdida de atomicidad.

---

## Preguntas abiertas

### P1. Skill descriptions iniciales
Las 20 skills viven en `data/skills.yaml` con `description: "TODO: operator-defined"`. El operador las escribe a medida que las usa por primera vez, o hacemos una sesión dedicada antes del V1? Bloquea `min_level` para ser interpretable por el LLM.

**Opciones:**
- (a) Sesión dedicada — 20 descriptions en una tarde
- (b) A demanda — se rellenan según entran proyectos
- (c) Pre-rellenar yo con drafts + tú revisas

**Mi recomendación:** (c) — te paso 20 drafts y tú editas los que te chirríen.

### P2. Roles de assignment: ¿acotados a 4?
Actualmente `lead|executor|reviewer|shadow`. ¿Falta alguno? ¿`mentor`? ¿`consultant` para apoyo puntual?

### P3. Estimated hours: ¿se usa para algo en V1?
El campo existe en Project pero ningún endpoint lo usa. ¿Queremos un check "assigned % × semanas vs estimated_hours" que alerte si hay sobreasignación de horas? O esto es V2.

### P4. Políticas de over-allocation (>100%)
El sistema lo permite y lo pinta rojo. ¿Alguna regla dura (bloquear apply) o solo visual?

### P5. Unarchive
Si alguien archivado quiere volver, ¿journal `person_unarchive` o se reutiliza `person_archive` con `archived: false`? El modelo actual acepta el segundo — cerrar si prefieres.

### P6. Backup de YAML
Los `.bak` se sobreescriben en cada apply. ¿Queremos un historial de backups (`.bak.YYYYMMDDHHMMSS`)? Git ya los versiona, así que probablemente innecesario.

### P7. Export / import de datos
¿Casos de uso? Mover datos a una instancia nueva, compartir con un colega externo… probable V2.

### P8. Próximo bloque
Wire-up parcial en curso: Journal ya va live. Decidir siguiente slice:
(a) completar wire-up del resto de páginas (mecánico, 1 día),
(b) añadir los 4 modales `*_update` que faltan (edit-person/project/client + required_skills editor),
(c) saltar al LLM chat (SSE + tool-loop contra Ollama),
(d) admin pages de skill catalog y oficinas.

### P10. LLM debe conocer el catálogo dinámicamente
Ahora que `skill_catalog_create`/`archive` existen, el system prompt del LLM no puede contener las 20 skills como texto fijo. Opciones:
- (a) Al iniciar la sesión, inyectar el catálogo actual como mensaje system con `label_es + description + archived`.
- (b) Añadir un tool `list_skills()` y obligar a la LLM a usarlo antes de proponer `skill_update`.
- (c) Mantener la lista fija y aceptar que skills nuevas tardan en "entrar en la conversación" hasta reinicio.

Recomendación: (a) para V1 — simple y suficiente con catálogo pequeño.

### P9. Modales `*_update` — **RESUELTO 2026-04-19**
Construidos los 5 modales `*_update` (persona, proyecto, cliente, required_skills, skill_label). Cada uno hace diff contra el original y envía solo campos modificados. Archive+recreate ya no es necesario para ediciones.
