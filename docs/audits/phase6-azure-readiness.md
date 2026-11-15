# Fase 6 — preparación de Azure

Actualización del 2026-11-14: se habilitó ACS Email únicamente en el entorno de validación. Ver la sección «Correo transaccional ACS en Azure» para el estado vigente; las afirmaciones anteriores sobre correo deshabilitado describen el estado anterior a esta actualización.

## Alcance de este bloque

Preparación local y reversible de imágenes de contenedor para FastAPI y Next.js, más una verificación de la arquitectura actual. No se creó ningún recurso de Azure, no se configuraron secretos ni dominios y no se ejecutó un despliegue.

Fase 5B se mantiene en el estado documentado previamente; esta entrega no la cierra.
Fase 3B, incluidos T-02 y T-03, continúa PARTIAL. Este trabajo no valida datos institucionales ni declara el sistema listo para producción.

## Estado actual verificado

- El despliegue documentado y `render.yaml` usan Render, PostgreSQL administrado allí, storage S3 compatible, correo y Firebase.
- No existían Dockerfiles, configuración de Azure, IaC ni workflow de despliegue Azure.
- FastAPI requiere Python 3.12; el servicio Render usa dos workers y el engine PostgreSQL está configurado por proceso con pool 20 y overflow 10.
- La aplicación ejecuta seeds/sincronización del catálogo, limpieza de tokens y tareas en el `lifespan`. La limpieza de rate-limit corre por proceso; el recordatorio interno también puede correr por proceso. El endpoint protegido `/api/v1/notifications/cron/vaccine-reminders` permite usar un scheduler externo, pero antes de escalar debe ser el único disparador de recordatorios.
- Next.js es una aplicación Node.js con BFF dinámico, usa `pg` para sesiones y necesita `API_INTERNAL_URL`, `BFF_ORIGIN`, `BFF_DATABASE_URL` y `BFF_SESSION_KEY` en runtime. No es un sitio estático.
- Evidencias y certificados usan la abstracción de almacenamiento actual: local o S3. No existe aún adaptador privado para Azure Blob/Managed Identity.
- El health check `/` valida conectividad con la base de datos y responde 503 si no está disponible.
- No se detectaron `az`, Bicep ni Docker Compose. Docker está instalado, pero el usuario del entorno no tiene acceso al socket Docker, por lo que las imágenes aún no se pudieron construir localmente.
- La versión instalada de Node es 22 y CI fija Node 20; la imagen Next se alinea con CI. Next 16 requiere Node >=20.9.

## Arquitectura objetivo propuesta

```text
Flutter ────────────────┐
                        ├─ HTTPS → Azure Container Apps: FastAPI (ingress público)
Navegador → ACA: Next BFF┘                         │
                                                   ├─ PostgreSQL Flexible Server
                                                   ├─ Blob privado (Managed Identity)
                                                   ├─ Key Vault (secrets referenciados)
                                                   └─ Monitor / Log Analytics

GitHub Actions ─ OIDC ─ ACR ─ imágenes ─ ACA
Container Apps Job ─ recordatorios programados (UTC) ─ API protegida
```

La API sigue siendo la autoridad. La conexión de Next a FastAPI debe usar el nombre interno de la API cuando la topología de red elegida lo permita; clientes Flutter requieren una URL HTTPS pública estable. Blob debe permanecer privado y las descargas deben seguir pasando por autorización FastAPI. Las identidades administradas deben reemplazar claves de storage donde sea posible. Los secretos externos que no soportan identidad administrada permanecen en Key Vault.

La programación de Container Apps Jobs usa UTC; la tarea diaria debe calcular fechas clínicas con `America/Bogota` dentro de la aplicación y el horario del Job debe configurarse teniendo en cuenta el desfase institucional.

## Cambios locales de este bloque

- `backend/Dockerfile`: imagen Python 3.12, usuario sin privilegios, dependencias declaradas y arranque Gunicorn/Uvicorn con un worker.
- `backend/.dockerignore`: excluye entornos, archivos locales, datos, pruebas y posibles credenciales del contexto de imagen.
- `frontend-next/Dockerfile`: imagen multi-stage Node 20, build standalone, runtime no-root.
- `frontend-next/.dockerignore`: excluye entorno local, dependencias y artefactos de build del contexto.
- `frontend-next/next.config.ts`: habilita el output standalone requerido por la imagen Node.
- `.github/workflows/ci.yml`: compila ambas imágenes en CI sin publicarlas ni desplegarlas.

## Bloqueos y riesgos antes de desplegar

1. **Storage:** implementar y probar Azure Blob privado con Managed Identity; planear migración y reconciliación de objetos desde S3. No cambiar `STORAGE_TYPE` hasta tener pruebas de lectura/escritura/autorización y rollback.
2. **Startup:** separar seeds y sincronización del catálogo de cada arranque de API. Deben ser una operación explícita, idempotente y ejecutada una sola vez. Hasta entonces no habilitar despliegues con réplicas/revisiones simultáneas.
3. **Tareas:** deshabilitar el loop de recordatorios dentro de los workers y usar una sola tarea programada; comprobar idempotencia concurrente antes de programarla.
4. **Conexiones:** parametrizar/medir el pool SQLAlchemy y el pool `pg` de Next contra el máximo de conexiones del plan PostgreSQL y el máximo de réplicas. El valor actual podría multiplicarse por worker y réplica.
5. **Migraciones:** ejecutar Alembic como paso único previo al tráfico, con copia recuperable y prueba de restauración. No ejecutar migraciones automáticamente por cada réplica.
6. **Red/identidad:** faltan decisiones verificables sobre región/data residency, dominio, presupuesto, entornos y conectividad privada. No inventar esos valores ni abrir firewall al público por defecto.
7. **CI/CD:** añadir después autenticación GitHub→Azure mediante OIDC y permisos mínimos. No almacenar credenciales Azure duraderas en GitHub.
8. **Datos:** T-02/T-03 requieren validación institucional autorizada; por tanto, cualquier despliegue durante esta fase debe ser entorno de prueba con datos sintéticos.
9. **Operación:** faltan estrategia de backups/PITR, retención, alertas, runbook y procedimiento de rollback/cutover desde Render.

## Plan de bloques de Fase 6

| Bloque | Entregable | Gate |
|---|---|---|
| 6A | Imágenes de API y BFF reproducibles, build en CI | Ambas imágenes construyen y no incluyen secretos |
| 6B | Adaptador Azure Blob privado y pruebas con emulador/cuenta de prueba | Tests de upload/download/delete y autorización, sin endpoint público |
| 6C | Separar bootstrap y tareas periódicas de los workers | Pruebas de concurrencia/idempotencia y arranque en múltiples réplicas |
| 6D | IaC parametrizada para entorno no productivo (ACA, PostgreSQL, Storage, Key Vault, ACR, observabilidad) | Validación del template y revisión de red/coste antes de provisionar |
| 6E | Workflow CI/CD con OIDC, migración única, despliegue gradual y smoke tests | Aprobación humana y secretos externos configurados por el propietario |
| 6F | Ensayo de migración y cutover de staging desde Render | Backup restaurado, conteos/checksums reconciliados, rollback ensayado |
| 6G | Producción | Bloqueado por T-02/T-03, validación de almacenamiento real, decisiones institucionales y aprobación explícita |

## Verificación inicial de la fase — 2026-11-07, antes del aprovisionamiento

- Next: `npm test` **PASS** (582 passed, 3 skipped), `npm run lint` **PASS**, TypeScript `tsc --noEmit` **PASS**, `next build --webpack` **PASS**.
- Flutter: `flutter analyze --no-pub` **PASS**; `flutter test --no-pub` **PASS**.
- Backend: Ruff check **PASS** y format check **PASS**. Pytest en SQLite **PASS** (380 passed, 37 skipped; 7 warnings). No se ejecutó PostgreSQL real; el motivo individual de cada skip no se recopiló para esta ejecución.
- `docker build backend`: **BLOCKED**, socket Docker inaccesible para este usuario del entorno.
- `docker build frontend-next`: **BLOCKED**, misma causa; la compilación queda configurada como gate de CI.
- En esa verificación inicial no se ejecutaron comandos `az`, despliegues, migraciones de datos ni llamadas a recursos externos.
- Estado de Fase 6 en esa fecha: **IN PROGRESS — 6A PREPARED, CONTAINER BUILDS NOT VERIFIED**.

## Rollback

El rollback de esta verificación inicial solo cubría los cambios aditivos de código: Dockerfiles, `.dockerignore`, job de build y `output: standalone`; los servicios Render y artefactos no cambiaban. El entorno Azure creado posteriormente se describe en la sección siguiente y tiene un ciclo de rollback separado.

## Seguimiento de publicación y preflight de Azure — 2026-11-07, antes del aprovisionamiento

- El repositorio `LUISDACA/azureimmunoclinic` estaba vacío y es público. El snapshot inicial publicado en `main` no tiene padres; no se publicó el historial previo sin auditar.
- CI inicial: backend tests/Ruff **PASS**; Next tests/lint **PASS**; imagen FastAPI **PASS**.
- En CI del commit `f64e923`: backend tests/Ruff **PASS**; Next tests/lint **PASS**; imágenes FastAPI y Next **PASS**. La causa del fallo de imagen Next quedó resuelta al incluir los fixtures sintéticos requeridos desde el contexto raíz.
- Flutter CI: **433 PASS / 14 FAIL**, todos en goldens de comunicaciones/contraste con diferencias pixel pequeñas (0.06–0.12%). No se modificó la UI para silenciar esos fallos; Fase 5B conserva su validación manual pendiente.
- El usuario selecciona Azure for Students y prioriza costo bajo. La oferta pública consultada indica USD 100 para usar en los primeros 12 meses, limitado a usos educativos/desarrollo/prueba/demostración y con restricciones para prestar servicios a terceros. Por ello no se usará esa suscripción para producción clínica sin confirmación de elegibilidad institucional/Microsoft. Fuente: [Azure for Students — condiciones de la oferta](https://azure.microsoft.com/en-us/pricing/offers/ms-azr-0170p).
- Como referencia no vinculante de costo, la página pública de PostgreSQL Flexible Server muestra B1ms en USD 12.41/mes antes de almacenamiento, respaldo, red y variación regional. El costo debe recalcularse para la región aprobada antes de crear recursos. Fuente: [precios de PostgreSQL Flexible Server](https://azure.microsoft.com/en-us/pricing/details/postgresql/flexible-server/).
- Azure Container Apps Consumption ofrece una subvención mensual de consumo, con cargos cuando excede los límites o se mantiene una réplica mínima activa. Fuente: [precios de Azure Container Apps](https://azure.microsoft.com/en-us/pricing/details/container-apps/).
- Azure CLI 2.92.0 está instalado de forma temporal bajo `/tmp/immuno-miguel-tools/azure-cli-tool` usando Python 3.12 local. No se instaló ningún paquete global. La sesión Azure sigue sin autenticarse y no se creó ningún recurso; Bicep tampoco está instalado.
- Para avanzar con un entorno no productivo hacen falta región permitida por la institución y nombre/autorización del resource group. Los créditos disponibles deben verificarse dentro de la cuenta antes de provisionar. T-02/T-03 de Fase 3B siguen PARTIAL; no se migrarán datos institucionales ni se afirmará preparación productiva hasta validarlos y acordar el origen/restauración de datos.

## Entorno Azure aislado para validación T-02/T-03 — 2026-11-07 a 2026-11-10

El usuario autorizó usar Azure for Students en **Brazil South** para un entorno aislado de validación. Esta autorización no convierte el entorno en producción ni cierra T-02/T-03.

- Resource group: `rg-immunoclinic-validation`.
- App Service Linux B1 / Python 3.12: `ic-validation-6uj5qzgnzi`.
- PostgreSQL Flexible Server 17 B1ms, red privada y base `immunoclinic`: `pg-ic-validation-6uj5qzgnzi`.
- Storage Blob privado, sin acceso público a blobs ni shared key: `icvalidation6uj5qzgnzi`.
- Key Vault con soft delete y purge protection: `kv-ic-val-6uj5qzgnzi`.
- API: `https://ic-validation-6uj5qzgnzi.azurewebsites.net`; la ruta `/` devolvió HTTP 200 y `status: healthy` después de corregir el comando y desactivar bootstrap.
- El primer ZIP deploy respondió HTTP 504 desde Kudu, pero la operación remota concluyó en estado de éxito. La primera ejecución de Alembic falló porque el script de consola no resolvió el paquete `app` desde el directorio temporal de Oryx. El comando se cambió a `python -m alembic` y `python -m gunicorn` y se verificó configurado en App Service.
- Después del primer arranque correcto, `STARTUP_BOOTSTRAP_ENABLED` se cambió a `false`; se verificó el valor y el health check volvió a `healthy`. Los reinicios posteriores no vuelven a sembrar/sincronizar catálogo ni administrador.
- Las restricciones del App Service y SCM son por IP `/32`. La IP de esta estación cambió; tras renovar MFA, se reemplazaron ambas reglas y se verificó que apuntan a la IP actual. La acción por defecto sigue siendo **Deny** para API y SCM; no se abrió el acceso globalmente.
- Los logs se habilitaron temporalmente para diagnóstico. La causa raíz del nivel residual fue que la operación anterior no actualizó `applicationLogs.fileSystem.level`. El 2026-11-10 se aplicó una actualización puntual a la configuración `config/logs` de App Service y se volvió a leer el estado efectivo: filesystem, Blob y Table en `Off`; HTTP logs desactivados; errores detallados y failed-request tracing desactivados. Bicep declara el mismo estado deseado en `appLogs`; no se reaplicó toda la plantilla. No se copiaron credenciales ni logs al repositorio y no se han cargado datos clínicos.
- El primer arranque aplicó las migraciones de Alembic sobre una base nueva. No se importó ningún dataset institucional, ni se creó información clínica de estudiantes.
- El email inicial `admin@immunoclinic.validation.invalid` era rechazado por `EmailStr` (HTTP 422). Se actualizó el email de la única cuenta bootstrap sintética en PostgreSQL a `admin@immunoclinic.example.com`, se alinearon el setting App Service y el default Bicep, y se verificó login HTTP 200 + logout HTTP 200. Los tokens de la prueba se descartaron; no se cambió la contraseña. La contraseña sintética permanece solo en un archivo temporal protegido de esta estación; no se incluye en documentación ni en el repositorio.

### Estado, riesgos y siguiente paso

**Estado del entorno: READY FOR MANUAL VALIDATION desde la estación allowlisted; NOT PRODUCTION.** Recursos, migraciones de base vacía, health check y login/logout están verificados. API y SCM siguen limitados a una IP `/32`; para otras estaciones debe actualizarse la allowlist explícitamente. La lectura posterior a la actualización puntual confirmó todos los destinos de logs en `Off`/desactivados.

**Datos: NONE LOADED.** Aunque existe autorización para un entorno con datos reales, no se recibió ni cargó un dataset institucional. T-02 y T-03 siguen **PARTIAL**. Para validarlos se necesita una exportación institucional aprobada, con origen documentado, snapshot previo protegido, conciliación ANTES/DESPUÉS y revisión de las diferencias por responsable institucional. No cargar datos de producción directamente ni declarar validación solo por disponer del entorno.

**Límites actuales:** Next está publicado en Vercel (evidencia: captura del usuario, `/login`), pero el login devuelve 503. Flutter no se desplegó; correo ACS está habilitado solo para validación, mientras FCM y recordatorios siguen deshabilitados; CORS está vacío; no se configuraron dominios institucionales, CI/CD, backups de producción, monitorización operativa ni recuperación probada. La API de Azure permanece restringida a una estación.

**Coste y elegibilidad:** el entorno consume créditos de Azure for Students; no se verificó el saldo, el costo mensual real ni la elegibilidad para producción clínica. No se habilitó PAYG. Debe revisarse el costo en Cost Management y apagar los servicios cuando no se usen. La base usa backup local de siete días, sin geo-redundancia ni alta disponibilidad; no usar para operación clínica.

**Rollback:** al ser un entorno vacío, puede detenerse/eliminarse el App Service y PostgreSQL si se abandona la prueba. La eliminación de Key Vault tiene retención y protección contra purge; no purgarlo manualmente. Si ya se carga un dataset autorizado, detener escrituras, exportar y proteger evidencia, decidir conservación con la institución y solo después eliminar recursos.

### Verificación local de infraestructura

- Bicep lint: **PASS** para `infra/azure/validation-appservice.bicep`.
- Backend: las pruebas de arranque con `STARTUP_BOOTSTRAP_ENABLED` deshabilitado/habilitado habían pasado (2 tests); no se ejecutó una nueva suite completa durante el aprovisionamiento.
- Azure CLI se reautenticó mediante MFA el 2026-11-10. Allowlist, health check y login/logout se verificaron después de renovar la sesión.
- Configuración efectiva de logs consultada en Azure el 2026-11-10: application filesystem/Blob/Table **Off**, HTTP logs **false**, detailed errors **false**, failed-request tracing **false**.
- `infra/azure/validation-appservice.bicep` declara `STARTUP_BOOTSTRAP_ENABLED=false`, el email sintético aceptado por `EmailStr` y la configuración de logs desactivada. La plantilla completa no se volvió a desplegar porque `what-if` detectó siete cambios adicionales fuera del alcance (PostgreSQL/Storage); no se aplicaron esos cambios.
- Un `what-if` de reconciliación completa del template predijo siete modificaciones adicionales, incluidas propiedades omitidas de PostgreSQL/storage; no se aplicó esa reconciliación. Se actualizaron las reglas de acceso y el email mediante operaciones puntuales para evitar cambios ajenos al objetivo.

## Vercel y acceso al backend — 2026-11-10

- Una captura proporcionada por el usuario confirma que `https://azureimmunoclinic.vercel.app/login` carga. El intento de autenticación muestra el mensaje seguro de servicio no disponible (503); no demuestra un rechazo de contraseña.
- Causa raíz visible en el código: el BFF requiere `API_INTERNAL_URL`; el almacenamiento de sesión también requiere `BFF_DATABASE_URL` y `BFF_SESSION_KEY` (`frontend-next/src/app/api/[...path]/route.ts`, `frontend-next/src/lib/server/session.ts`). Las excepciones de configuración/conectividad se convierten en 503. Los valores runtime y logs de funciones de Vercel son **UNKNOWN** desde esta sesión.
- Hay además una incompatibilidad de red conocida: el App Service solo permite la estación allowlisted y PostgreSQL Flexible Server es privado. No se habilitó acceso público ni se añadió un allowlist amplio para Vercel. Mientras no exista conectividad privada o egreso estático aprobado y verificable para BFF/API/DB, Vercel no debe considerarse operativo con datos.
- La captura expuso una credencial del administrador sintético. Se rotó por `POST /api/v1/auth/change-password` usando HTTPS desde la estación permitida; respuesta **200** y sesiones/tokens anteriores invalidados por el flujo de dominio. No se imprimió la nueva clave; queda únicamente en el archivo local protegido de esta estación.
- El intento de actualizar el secreto `admin-password` de Key Vault fue rechazado con `ForbiddenByRbac`; no se ampliaron roles. `STARTUP_BOOTSTRAP_ENABLED=false` sigue vigente, por lo que el secreto bootstrap no vuelve a sembrar la cuenta. Su rotación en Key Vault queda pendiente de un actor con permiso `setSecret`.

**Estado:** frontend Vercel publicado; autenticación funcional **BLOCKED** por configuración/conectividad de runtime; causa exacta del 503 **UNKNOWN** hasta revisar variables y logs de Vercel. No abrir el backend ni la base a todo Internet para resolverlo.

## Next BFF en Azure para validación — 2026-11-11

### Causa raíz del 503

- Se desplegó Next en Azure para mantener FastAPI y el almacenamiento BFF dentro de la red privada. El 503 posterior al primer despliegue no era un rechazo de contraseña.
- La referencia `BFF_DATABASE_URL` resolvió desde Key Vault. Su URI usa el formato del backend `postgresql+asyncpg://...?...ssl=require`.
- `node-postgres` interpreta `ssl=require` como una cadena en la opción TLS; al abrir PostgreSQL lanzaba `TypeError: Cannot use 'in' operator to search for 'key' in require`.
- `frontend-next/src/lib/server/session.ts` ahora convierte el prefijo SQLAlchemy a `postgresql://` y `ssl=require` a `sslmode=require`. No cambia FastAPI, la política clínica ni el contrato HTTP.

### Recursos y red

- Next App Service: `ic-next-validation-6uj5qzgnzi`, Linux Node 20, plan B1 separado, Brazil South. Se separó porque el plan existente registraba picos de 99% de CPU y 95% de memoria en la consulta previa.
- Acceso al sitio y SCM: solo la estación autorizada `/32`; HTTPS habilitado. El sitio no está abierto a Internet de forma general.
- El plan Next está integrado con la subred dedicada `appservice-next` para PostgreSQL Flexible Server privado.
- Next llega a FastAPI por el Private Endpoint `pe-ic-validation-api` y DNS privado `privatelink.azurewebsites.net`. La lista pública de acceso de FastAPI conserva su regla de estación y `Deny` por defecto; no se agregaron IPs de salida compartidas.
- La identidad administrada de Next solo recibe `Key Vault Secrets User` sobre el secreto `database-url`. La referencia de runtime figura como `Resolved`.
- `BFF_SESSION_KEY` se generó con 32 bytes aleatorios y se configuró en App Service; el archivo temporal tuvo permisos `0600` y no está en el repositorio. No se concedió permiso amplio para escribir secretos en Key Vault.
- No se cargaron datos clínicos ni se habilitó bootstrap.

### Build y pruebas

- `npm run build -- --webpack`: **PASS**.
- `node node_modules/typescript/bin/tsc --noEmit`: **PASS**.
- `npm run lint`: **PASS**.
- `npm test -- src/lib/server/__tests__/session.test.ts`: **4 PASS, 2 SKIP**; los dos tests que requieren PostgreSQL local no recibieron `BFF_TEST_DATABASE_URL`.
- Suite completa Next después de la corrección: `npm test` **584 PASS, 3 SKIP**.
- Build standalone empaquetado en ZIP: **2.455 archivos**, sin archivos `.env`.
- Despliegue ZIP al App Service: **PASS**; Azure informó `Deployment has completed successfully`.
- Smoke HTTP desde la estación autorizada: `/login` **200**, `/api/auth/csrf` **200**, login con usuario sintético inexistente **401** (FastAPI, no 503).
- Consulta de sesión con cookie aleatoria inexistente: **401** después de consultar `web_sessions`. Esto verifica conexión TLS y lectura BFF→PostgreSQL sin crear ni modificar sesiones.
- No se realizó login válido con una cuenta real/sintética porque no se usaron credenciales reales en esta prueba. El usuario puede probarlo manualmente.

La clave BFF se mantiene como App Setting protegida, no en Key Vault: el operador autenticado no tiene permiso `setSecret` y no se amplió IAM para concederlo. La clave es aleatoria, no se guarda en el repositorio y el valor no se consultó ni se imprimió. Para rotarla hay que coordinar el cambio con las sesiones almacenadas, porque estas se cifran con esa clave.

### Estado y límites

**Azure Next: READY FOR MANUAL VALIDATION** en [https://ic-next-validation-6uj5qzgnzi.azurewebsites.net/login](https://ic-next-validation-6uj5qzgnzi.azurewebsites.net/login), accesible desde la estación allowlisted. Vercel sigue publicado, pero no tiene la conexión privada a API/PostgreSQL y no se modificó su configuración.

T-02/T-03 continúan **PARTIAL**. Este despliegue no usa ni valida dataset institucional y no declara producción lista. El costo mensual exacto y el saldo actual de créditos siguen **UNKNOWN**; revisar Cost Management y detener el plan si no se usa.

### Rollback

- Código: reconstruir y desplegar el ZIP de la revisión anterior desde Git; el despliegue inicial tenía el defecto TLS descrito arriba.
- App Next y costo: detener/eliminar solo `ic-next-validation-6uj5qzgnzi` y `asp-ic-next-validation-6uj5qzgnzi`. Antes de borrar `appservice-next`, quitar la integración VNet del App Service.
- Red privada opcional: eliminar el Private Endpoint `pe-ic-validation-api`, el grupo DNS asociado, el enlace de `privatelink.azurewebsites.net` y su subred `appservice-private-endpoints`.
- No borrar ni reconfigurar FastAPI, PostgreSQL, su zona DNS existente, Storage ni Key Vault durante el rollback de Next.

## Acceso público del frontend y recuperación de cuenta sintética — 2026-11-12

- El 403 mostrado en el navegador era el bloqueo de Access Restrictions: la IP de salida de la estación había cambiado. A petición explícita del usuario se dejó Next (`ic-next-validation-6uj5qzgnzi`) accesible desde cualquier IP: acción predeterminada `Allow` y regla efectiva `Allow all`. El smoke HTTP de `/login` desde esta estación devolvió **200**; la configuración de Azure permite otras IP, aunque no se pudo hacer una prueba de navegador desde una segunda red.
- SCM quedó separado del sitio público (`scmIpSecurityRestrictionsUseMain=false`), con acción predeterminada `Deny`, regla `Deny all` y una única regla `/32` de esta estación para operaciones de despliegue. FastAPI permanece con acción `Deny`, su allowlist `/32` y `Deny all`; PostgreSQL sigue privado. No se abrieron API, SCM ni base de datos al público.
- Por solicitud del usuario se rotó la contraseña de la única cuenta bootstrap sintética `admin@immunoclinic.example.com`. La operación bloqueó la fila del usuario y, en la misma transacción, cambió el hash, incrementó `auth_version`, revocó sesiones/tokens, invalidó resets pendientes, desactivó tokens de dispositivo, marcó sesiones BFF como revocadas y añadió auditoría `password.reset` sin PII en detalles. La nueva contraseña se guardó fuera del repositorio en `/tmp/immuno-miguel-tools/validation-admin-login.txt` con modo `0600`; no se registra aquí.
- Verificación real posterior: login y logout vía `AuthService` correctos; flujo BFF Azure: CSRF **200**, login **200**, `/api/users/me` **200**, logout **204**. No se imprimieron tokens ni datos de perfil.
- Rollback de acceso público: en Next, configurar la acción predeterminada del sitio en `Deny` y reinstalar `Deny all`; conservar solo allowlists `/32` autorizadas. Mantener SCM separado y denegado por defecto. La clave no debe restaurarse a la anterior; ante pérdida del archivo se requiere otra rotación con revocación de sesiones.
- Aunque la página de login del frontend es pública, el entorno continúa siendo solo de validación; T-02/T-03 siguen **PARTIAL** y no se cargaron datos institucionales. El acceso público a la página no hace públicas las sesiones ni los datos clínicos, que requieren autenticación y autorización.

## Correo transaccional ACS en Azure — 2026-11-14

### Alcance y configuración

- Se habilitaron correos de alta para estudiantes y administradores normales. El backend genera la contraseña temporal, almacena su hash, exige cambiarla en el primer inicio y envía el correo después del commit. La contraseña no aparece en respuestas API, auditoría ni logs.
- Se añadió un transporte Azure Communication Services Email para FastAPI. Usa `DefaultAzureCredential` con la identidad administrada del App Service; no se configuraron claves, secretos ni connection strings de ACS. Cuando ACS está configurado, un fallo no cae silenciosamente a SendGrid o SMTP.
- Recursos aislados en `rg-immunoclinic-validation`: Email Service `ic-email-validation-6uj5qzgnzi`, dominio administrado `AzureManagedDomain` y Communication Service `ic-comm-validation-6uj5qzgnzi`. `Microsoft.Communication` quedó registrado en la suscripción. El dominio se verificó en SPF, DKIM, DKIM2 y DMARC; el tracking de interacción está deshabilitado y la ubicación de datos es Brazil.
- Remitente de validación: `DoNotReply@286f1e11-bee4-458e-b739-cfe98892edad.azurecomm.net`. El dominio administrado no requiere cambios DNS, pero no es un remitente institucional personalizado.
- A la identidad administrada de `ic-validation-6uj5qzgnzi` se le asignó el rol custom `ImmunoClinic ACS Email Sender Validation`, limitado al recurso `ic-comm-validation-6uj5qzgnzi`, con acciones `CommunicationServices/read` y `CommunicationServices/write`. No se usó el rol amplio `Communication and Email Service Owner`.
- El paquete backend se desplegó por ZIP/Oryx. Kudu reportó despliegue activo `status=4`, completo y sin errores. El contenedor respondió `{"status":"healthy","app":"ImmunoClinic","version":"2.0.0"}` por loopback. Desde el contenedor, `DefaultAzureCredential` obtuvo un token para `https://communication.azure.com/.default`; el token no se imprimió.
- App Service quedó con `EMAIL_ENABLED=true`, `AZURE_COMMUNICATION_EMAIL_ENDPOINT` y `AZURE_COMMUNICATION_EMAIL_SENDER` configurados. API y SCM siguen `Deny` por defecto. La regla `/32` temporal de SCM usada para el ZIP deploy se retiró; no se cambió el acceso público del API.

### Verificación y límites

- Pruebas backend focales (correo, cuentas, Azure Blob y startup): **18 PASS**. Ruff check, Ruff format y `git diff --check`: **PASS**. Se ejecutaron pruebas con SMTP falso local; no se envió ningún correo de prueba a una persona.
- Está verificada la configuración del proveedor, el despliegue, el health check interno, el token de identidad y la respuesta de aceptación del adapter mediante mocks. **La entrega a una bandeja real sigue sin verificarse**; no se consultó un evento de entrega ni se pidió un destinatario para una prueba externa. Crear una cuenta real activará el envío del correo de alta, y el resultado de la API del proveedor no garantiza que el mensaje llegue a Inbox.
- Para el dominio administrado, Azure documenta un límite de 5 mensajes/minuto y 10 mensajes/hora, sin aumento de cuota. El precio publicado es aproximadamente **USD 0.00025 por email + USD 0.00012 por MB transferido**; la facturación efectiva depende del consumo y la región. Fuentes: [precios ACS](https://azure.microsoft.com/en-us/pricing/details/communication-services/) y [límites ACS Email](https://learn.microsoft.com/en-us/azure/communication-services/concepts/service-limits).
- Riesgo de ciclo de vida: Microsoft clasifica ACS Email como servicio en retiro, indica soporte hasta el **30 de septiembre de 2028** y recomienda migrar workloads existentes en vez de iniciar soluciones nuevas. Esta integración es **temporal y solo para validación**, no una decisión para producción. Fuente: [guía de retiro ACS](https://learn.microsoft.com/en-us/azure/communication-services/acs-retirement-and-breaking-changes-guide).
- Fase 3B sigue PARTIAL: T-02/T-03 no están cerrados, no se importó dataset institucional y este despliegue no declara producción lista.

### Rollback

1. Para detener inmediatamente todos los correos, establecer `EMAIL_ENABLED=false` en el App Service. Se puede retirar también el endpoint y remitente ACS; no hay datos de aplicación que migrar.
2. Para retirar el acceso de la aplicación, borrar su asignación del rol custom. Después, si se abandona la validación, borrar el Communication Service, el dominio y Email Service; no hacerlo mientras se requiera conservar evidencia de envíos.
3. El código no altera datos ni migraciones. No se conservó un ZIP anterior de la aplicación, así que el rollback probado es deshabilitar correo; restaurar una versión previa completa requerirá reconstruir y desplegar su artefacto anterior.

## Alta de administrador sin clave manual y aviso de sesión — 2026-11-14

### Causa raíz

- La integración de correo ya existía, pero el formulario Next seguía exigiendo `password` y la API también la exigía. Por eso al crear un administrador todavía se pedía una contraseña, a pesar de que el backend ya enviaba un correo de bienvenida.
- En `/login`, la restauración inicial de una cookie BFF vencida puede recibir 401 desde `/users/me`. El interceptor emitía `immuno:session-expired` también cuando la tienda no tenía ninguna sesión autenticada, por lo que la pantalla vacía mostraba el aviso de sesión expirada.

### Corrección y compatibilidad

- El formulario Next ya no captura ni envía contraseña. El backend acepta el campo como opcional y genera una credencial temporal aleatoria si está ausente; todavía acepta el campo para clientes anteriores durante la transición.
- La contraseña inicial solo se usa para guardar el hash y enviar el correo de bienvenida. `must_change_password` continúa activo y la respuesta `UserResponse`, la auditoría y los logs no incluyen la contraseña ni su hash.
- La tienda Next ahora ignora el evento de expiración mientras no exista una sesión autenticada; las respuestas 401 durante una sesión activa siguen limpiando la sesión y mostrando el aviso.
- No se enviaron correos de prueba ni se crearon cuentas reales durante esta verificación.

### Verificación

- Backend `tests/test_admin_accounts.py`: **5 PASS**; incluye generación cuando el campo se omite, hash, envío por correo simulado, cambio obligatorio y compatibilidad con clientes que todavía mandan contraseña.
- Next focal inicial: **57 PASS**. Suite completa: **586 PASS, 3 SKIP**. Tras añadir la instrucción visible se repitieron los tests de administración: **42 PASS**. TypeScript `--noEmit`, ESLint (suite inicial y lint focal final) y `next build --webpack` final: **PASS**.
- Ruff check y format para los archivos backend modificados: **PASS**. `git diff --check`: **PASS**.
- FastAPI se publicó en `ic-validation-6uj5qzgnzi`; Azure reportó `RuntimeSuccessful` y cero instancias fallidas. Next se publicó en `ic-next-validation-6uj5qzgnzi`; el último ZIP terminó con `status=4`, `complete=true`, sin errores ni warnings de build.
- Smoke del sitio publicado: `/login` **200**, `/api/auth/csrf` **200** y ejecución headless de la vista anónima: login visible, aviso de sesión expirada ausente. El chunk público de `/admin/admins` contiene la indicación del correo temporal y no tiene el campo de contraseña; los tests de componente verifican el payload POST sin contraseña.
- Para desplegar se añadieron reglas SCM `/32` temporales y luego se retiraron de ambos App Services. Verificación posterior: API SCM conserva la allowlist aprobada y `Deny all`; Next SCM conserva `current-workstation-scm` y `Deny all`. No se modificó la regla del sitio principal, PostgreSQL, API pública ni sus secretos.
- El smoke no creó cuentas ni envió correos reales. La entrega a una bandeja sigue **UNKNOWN** hasta que se cree una cuenta con un correo autorizado y se revise la recepción. No se usaron credenciales ni datos institucionales.
- No se desplegó a Vercel ni producción. T-02/T-03 permanecen **PARTIAL** y Azure sigue siendo solo validación.

## Enlace de acceso en correos de bienvenida — 2026-11-14

- **Causa raíz:** las plantillas de bienvenida de administrador y estudiante no contenían enlace. Aunque existía `FRONTEND_URL`, Azure no la tenía configurada; su default local es `http://localhost:3000`.
- Ambos correos ahora incluyen un enlace clicable y la URL visible como alternativa. La plantilla ACS genera texto plano desde el HTML, por lo que la URL visible también llega a clientes que muestran texto plano.
- `FRONTEND_URL` se agregó al ejemplo de entorno y al Bicep de validación; en el App Service quedó configurado como `https://ic-next-validation-6uj5qzgnzi.azurewebsites.net`.
- SMTP fake local: `tests/test_email_transport.py` **8 PASS**, incluyendo URL en los dos correos y URL conservada en el texto plano ACS. Ruff y compilación Bicep: **PASS**.
- El mensaje ya enviado no se puede editar retroactivamente; el destinatario puede abrir manualmente el login y usar la contraseña temporal de ese mensaje. Los siguientes correos incluirán el enlace actualizado.
- El ZIP del backend quedó desplegado en validación (`status=4`, `complete=true`). La salud de la API y el login web respondieron 200; un intento sintético inválido llegó al endpoint de login y recibió 401, confirmando el trayecto Next→FastAPI sin usar cuentas reales. No se envió correo de prueba ni se modificaron cuentas; la entrega real a una bandeja sigue **UNKNOWN**.

## Acceso global de la API de validación — 2026-11-14

- **Causa raíz del error de servicio:** el App Service de FastAPI tenía una allowlist de una sola estación y ninguna de las IPs de salida actuales o posibles del App Service Next coincidía. La configuración de firewall podía impedir que el BFF llegara a FastAPI.
- Se habilitó acceso desde cualquier IP al sitio público del API de validación, conforme a la solicitud del usuario. La autorización de datos sigue dependiendo de autenticación FastAPI, permisos por endpoint y la sesión BFF; esto no permite iniciar sesión sin una cuenta válida.
- SCM sigue restringido: `scmIpSecurityRestrictionsDefaultAction=Deny`, allowlist `validation-client-scm` y `Deny all`. La regla temporal `codex-temporary-email-deploy` se retiró tras el despliegue.
- `infra/azure/validation-appservice.bicep` ahora refleja la política: API pública con default `Allow`, SCM restringido al cliente aprobado.
- Verificación: API `/` **200**, frontend `/login` **200**, BFF `auth/csrf` **200** y solicitud con correo sintético inexistente **401** (el backend contestó; no se usó una cuenta real). La API y SCM conservan sus políticas separadas.
- **Riesgo/alcance:** el API de validación queda expuesto a tráfico de Internet y depende de sus controles de autenticación, autorización y rate limiting. Solo aplica a validación, no cambia producción.
- **Rollback:** volver `ipSecurityRestrictionsDefaultAction` a `Deny` y restaurar la regla `/32` aprobada de la estación (o las salidas necesarias del frontend) manteniendo SCM con default `Deny`. La regla de Bicep debe restaurarse de forma coherente si se revierte.
- Fase 3B sigue **PARTIAL** (T-02/T-03); este entorno continúa siendo solo de validación y no se declara listo para producción.

## Pantalla de cambio obligatorio de contraseña — 2026-11-14

- **Causa raíz:** `AppShell` consultaba notificaciones para mostrar contadores en todas las rutas administrativas y estudiantiles. Durante el cambio obligatorio, FastAPI correctamente bloquea esa consulta hasta que se cambie la contraseña; el 403 se mostraba como una alerta ancha sobre el formulario. Además, la navegación completa resaltaba el Dashboard en la ruta de cambio de contraseña.
- En `/admin/change-password` y `/student/change-password`, el shell ahora omite la consulta de módulos, oculta las navegaciones lateral y móvil, centra el formulario y no renderiza errores de notificaciones. Conserva encabezado, tema y menú de cuenta. FastAPI, permisos y reglas de cambio de contraseña no se modificaron.
- Tests de regresión: ambas rutas verifican que no se consulta notificaciones ni aparecen alertas, botones de reintento o enlaces de módulos. Suite Next: **588 PASS, 3 SKIP**; lint, TypeScript y `next build --webpack`: **PASS**.
- ZIP standalone Next desplegado al App Service de validación (`status=4`, completo). Smoke HTTP: `/login`, `/admin/change-password` y `/api/auth/csrf` **200**. La ruta autenticada necesita verificación visual manual de una sesión temporal real.
- SCM volvió a quedar con regla `/32` previamente aprobada y `Deny all`; la regla temporal usada para este despliegue fue retirada. No se cambiaron secretos ni datos.
- El usuario puede recargar la página de cambio obligatorio para ver el formulario sin el aviso 403 ni la navegación de módulos.

## Diagnóstico de FCM en backend de validación — 2026-11-15

- El emisor push ahora registra cuando no hay tokens activos, faltan credenciales o Firebase rechaza envíos. Para respuestas multicast registra cantidades de destinos, éxitos, fallos y códigos de error sanitizados; nunca registra tokens, contenido ni identificadores de usuario.
- El mensaje Android usa prioridad alta y el canal `immuno_clinic_updates`, que crea Flutter al iniciar. El título y el cuerpo del aviso son genéricos y no incluyen información clínica.
- El ajuste se desplegó en `ic-validation-6uj5qzgnzi` con estado `RuntimeSuccessful`, una instancia exitosa y cero fallidas; el endpoint de salud responde `healthy`.
- El servicio también registra tipo y código sanitizado de excepciones. No cambia contratos, reglas clínicas, esquema de base de datos ni configuración de FCM.
- Azure confirmó `FCM_ENABLED=true` y que existe `FIREBASE_CREDENTIALS_JSON`; el valor secreto no se leyó. El App Service `ic-validation-6uj5qzgnzi` quedó `RuntimeSuccessful`, con una instancia saludable y `/` respondiendo `healthy`.
- La publicación requirió una regla SCM temporal `/32`; se retiró al terminar. SCM conserva default `Deny`, la allowlist aprobada y `Deny all`. No se cambiaron secretos ni el acceso público de la API.
- El diagnóstico remoto sigue **PENDIENTE** hasta que se genere una notificación nueva después del despliegue. No se creó ni modificó ninguna cuenta o dato clínico. No hay cambios de esquema; rollback mediante redeploy del paquete de backend anterior.
