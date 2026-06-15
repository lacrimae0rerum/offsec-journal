# PRD — Admin UI

- **Feature:** Admin UI (gestión de usuarios y auditoría desde la web)
- **Proyecto:** OffSec Journal
- **Autor:** El Buscador de Problemas (Product Owner, Alfred Dev)
- **Fecha:** 2026-06-15
- **Estado:** Pendiente de aprobación
- **Fase siguiente:** Arquitectura (bloqueada hasta aprobación del PRD)

---

## 1. Problema

El backend de administración existe y funciona (`api/routes/admin.py`: listar/crear/actualizar usuarios y consultar eventos de auditoría), pero **no hay forma de usarlo sin escribir peticiones HTTP a mano**. La sección `/admin` de la web está vacía. En la práctica, un admin de team que necesita dar de alta a un compañero, cambiarle el rol, archivar a quien se va, o revisar quién ha intentado entrar, tiene que recurrir al CLI del servidor o a `curl`. Eso convierte una tarea cotidiana en una operación reservada a quien tiene acceso a la máquina.

**El problema en una frase:** el admin de un team no puede gestionar a sus usuarios ni revisar la auditoría sin acceso al servidor, porque la UI de `/admin` está vacía.

## 2. Objetivo

Construir la capa de frontend (vanilla HTML/CSS/JS) que conecta la sección `/admin` ya existente con los endpoints ya existentes, para que un admin autenticado gestione usuarios y revise eventos de auditoría de **su propio team** desde el navegador, sin tocar el servidor.

Alcance: **solo frontend**. No se construye ni se modifica backend (ya está) ni los wrappers JS de `web/api.js` (ya existen: `adminListUsers`, `adminCreateUser`, `adminPatchUser`, `adminAuthEvents`).

## 3. Contexto

- El backend impone el aislamiento multi-tenant: un admin de `offsec` no ve ni toca usuarios de `infosec`. La UI no necesita reimplementar esa lógica, pero **sí debe respetar el contrato** (p. ej. no ofrecer un selector de team al crear usuarios).
- Los eventos de auditoría con `team_id` NULL (sysadmin / unknown_user / untrusted_proxy) **no llegan** a estos endpoints: el backend ya los filtra por team. La UI simplemente muestra lo que recibe.
- La decisión D2 (framework de frontend) está aplazada: se mantiene vanilla JS. Nada de React/Next.
- El diseño debe seguir los patrones ya usados en el resto de páginas: tablas, modales (`openModal`/`closeModal` en `app.js`) y toasts (`_toast(message, kind)`).

## 4. Solución propuesta (alto nivel)

Dos bloques dentro de `<section id="page-admin">`:

1. **Usuarios:** una tabla con los usuarios del team, un botón para crear (abre modal), y acciones por fila para cambiar rol y archivar/desarchivar. Toggle para mostrar archivados.
2. **Auth-events:** una tabla con los eventos de auditoría, filtro por tipo de evento y paginación (limit/offset).

> El detalle de implementación (estructura del DOM, nombres de funciones, render) es responsabilidad del architect y del senior-dev. Este PRD define qué, no cómo.

## 5. Actor principal

**Admin autenticado de un team** (rol `admin`). Es quien gestiona el alta/baja de miembros y vigila la auditoría de su equipo. No es sysadmin (ese opera por CLI) ni un member normal (los endpoints le devuelven 403).

## 6. Historias de usuario

### HU-1 — Ver usuarios del team
**Como** admin de mi team,
**quiero** ver una tabla con los usuarios de mi team (username, rol, display name, email, estado),
**para** saber de un vistazo quién tiene acceso y con qué nivel.

### HU-2 — Crear un usuario
**Como** admin de mi team,
**quiero** dar de alta a un usuario nuevo (username, rol, display name, email) desde un formulario,
**para** incorporar a un compañero sin pedir acceso al servidor.

### HU-3 — Cambiar el rol de un usuario
**Como** admin de mi team,
**quiero** cambiar el rol de un usuario entre `admin` y `member`,
**para** ajustar sus permisos cuando cambian sus responsabilidades.

### HU-4 — Archivar y desarchivar usuarios
**Como** admin de mi team,
**quiero** archivar a un usuario que se va (y poder desarchivarlo y verlo con un toggle),
**para** retirarle acceso sin perder su histórico.

### HU-5 — Revisar la auditoría de acceso
**Como** admin de mi team,
**quiero** ver los eventos de auth de mi team, filtrarlos por tipo y paginar,
**para** detectar accesos sospechosos o fallidos sin abrir el servidor.

## 7. Criterios de aceptación (Given/When/Then)

### CA-1 — Carga de usuarios (HU-1)
**Given** un admin autenticado en `/admin`
**When** se abre la sección de usuarios
**Then** se muestra una tabla con los usuarios activos del team (username, rol, display name, email) ordenados como los devuelve el backend.

### CA-2 — Toggle de archivados (HU-1, HU-4)
**Given** un admin con usuarios activos y archivados en su team
**When** activa el toggle "mostrar archivados"
**Then** la tabla pasa a incluir también los usuarios archivados, marcados visualmente como tales; al desactivarlo, vuelven a verse solo los activos.

### CA-3 — Crear usuario válido (HU-2)
**Given** un admin con el modal de creación abierto y los campos username="dana", role="member", display_name="Dana Q", email="dana@x.io"
**When** confirma la creación
**Then** se llama a `adminCreateUser`, el modal se cierra, aparece un toast de éxito y la tabla de usuarios se refresca con la nueva fila.

### CA-4 — Crear usuario con username vacío (HU-2, negativo)
**Given** un admin con el modal de creación abierto y el campo username vacío
**When** intenta confirmar
**Then** la creación no se envía y se muestra un mensaje indicando que username es obligatorio.

### CA-5 — Username duplicado (HU-2, negativo)
**Given** un admin que intenta crear un usuario cuyo username ya existe
**When** confirma la creación y el backend responde 409
**Then** se muestra un toast de error legible (no un volcado crudo) y el modal permanece abierto para corregir.

### CA-6 — Cambiar rol (HU-3)
**Given** un admin viendo un usuario con rol `member`
**When** cambia su rol a `admin` y confirma
**Then** se llama a `adminPatchUser` con `{role:"admin"}`, la fila refleja el nuevo rol y aparece un toast de éxito.

### CA-7 — Archivar usuario (HU-4)
**Given** un admin viendo un usuario activo
**When** pulsa archivar y confirma la acción
**Then** se llama a `adminPatchUser` con `{archived:true}` y, con el toggle de archivados desactivado, la fila desaparece de la tabla.

### CA-8 — Filtrar auth-events por tipo (HU-5)
**Given** un admin en la sección de auth-events
**When** selecciona un tipo de evento en el filtro
**Then** se llama a `adminAuthEvents` con ese `event` y la tabla muestra solo eventos de ese tipo, reiniciando la paginación al inicio.

### CA-9 — Paginación de auth-events (HU-5)
**Given** una lista de auth-events con `total` mayor que el `limit` mostrado
**When** el admin avanza a la página siguiente
**Then** se solicita el siguiente bloque con el `offset` correcto y se actualiza el indicador de posición (p. ej. "mostrando 101–200 de N"); "anterior" se deshabilita en la primera página.

### CA-10 — Acceso sin permisos (negativo, transversal)
**Given** una llamada a un endpoint de admin que devuelve 403 (rol insuficiente o sesión perdida)
**When** la UI recibe la respuesta
**Then** no se rompe la página y se muestra un mensaje claro de que no se tienen permisos de administración, sin exponer detalles internos.

## 8. Métricas de éxito

- **Cero accesos al CLF/servidor** para alta, cambio de rol y archivado de usuarios de un team: el 100% de esas operaciones rutinarias se hacen desde la UI.
- **Cobertura funcional:** las 4 operaciones de usuarios (listar, crear, patch rol, patch archived) y las 2 de auth-events (filtro, paginación) operativas desde `/admin`.
- **Robustez de errores:** los 3 escenarios negativos del backend (400 username vacío, 409 duplicado, 403 sin permiso) se muestran como mensajes legibles, no como excepciones o pantallas rotas.
- **Consistencia visual:** la sección reutiliza los patrones existentes (tabla/modal/toast) — verificable por revisión, sin CSS nuevo divergente.

## 9. Fuera de alcance

- **Cualquier cambio de backend** o de los wrappers de `web/api.js` (ambos ya existen).
- **CRUD de teams** desde la UI: la gestión de teams sigue siendo solo por CLI del servidor.
- **Operaciones cross-team:** un admin no puede crear ni gestionar usuarios de otro team; no habrá selector de team en el formulario de creación.
- **Eventos de auditoría con `team_id` NULL** (sysadmin / unknown_user / untrusted_proxy): no se muestran (el backend ya los excluye).
- **Borrado físico de usuarios:** solo existe archivar/desarchivar.
- **Edición de display_name/email de un usuario existente:** el backend solo permite patch de `role` y `archived`; editar otros campos queda fuera.
- **Exportación de auth-events, gráficas o alertas:** solo tabla, filtro y paginación.
- **Decisión D2 (migrar a React/Next u otro framework):** sigue aplazada.

## 10. Riesgos y dependencias

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| La UI ofrece campos que el backend no acepta en PATCH (display_name/email) | Confusión y errores 400/silenciosos | Limitar las acciones de edición a `role` y `archived`, según el contrato real del endpoint. |
| Mostrar errores como volcado crudo (status + body) | Mala UX, fuga de detalles internos | Mapear 400/409/403 a mensajes legibles vía `_toast`. |
| Paginación con `offset` mal calculada al combinar con el filtro de evento | Datos saltados o repetidos | Reiniciar `offset=0` al cambiar el filtro; calcular siguiente/anterior desde `total/limit/offset` que devuelve el backend. |
| Divergencia visual respecto al resto de páginas | Inconsistencia de producto | Reutilizar patrones existentes (`openModal`/`closeModal`, `_toast`, clases de tabla actuales). |
| Un admin asume que ve toda la auditoría (también NULL/sysadmin) | Falsa sensación de cobertura | El alcance deja explícito que los eventos sysadmin no aparecen; documentar en la propia UI si procede. |

**Dependencias:** ninguna externa. Todo el backend y los wrappers JS necesarios ya están en `api/routes/admin.py` y `web/api.js`.

## 11. Preguntas abiertas

Ninguna que afecte al alcance. (Detalle menor a decidir en arquitectura: tamaño de página por defecto para auth-events — el backend usa `limit=100`.)

---

## Gate de aprobación

Este PRD no avanza a arquitectura hasta aprobación explícita del usuario.

**VEREDICTO: APROBADO CON CONDICIONES**

**Resumen:** El PRD está completo (problema, objetivo, actor, 5 historias, 10 criterios, fuera de alcance y riesgos) y acotado a frontend sobre backend ya existente.

**Hallazgos bloqueantes:** ninguno.

**Condiciones pendientes:** aprobación explícita de Fer; confirmar el tamaño de página por defecto de auth-events (sugerido: 100, alineado con el backend).

**Próxima acción recomendada:** revisión de Fer. Si aprueba, pasa al architect como input de diseño. Si no, se itera sobre los puntos marcados.
