# Publicación privada del cotizador Kelly en Render

La arquitectura preparada usa tres recursos pagados: un servicio web Next.js, un servicio privado FastAPI y PostgreSQL administrado. Ninguno utiliza el plan gratuito, por lo que no se suspende por inactividad. El único punto público es Next.js; FastAPI y PostgreSQL permanecen en la red privada de Render.

## 1. Preparar GitHub

1. Crea un repositorio **privado** en GitHub.
2. Sube este proyecto completo, excepto los archivos ignorados por `.gitignore` (`.env`, bases `.db`, respaldos y dependencias).
3. Confirma que `render.yaml` está en la raíz del repositorio.

## 2. Crear el Blueprint, sin publicar todavía

1. En Render abre **New → Blueprint**.
2. Conecta GitHub y selecciona el repositorio privado.
3. Render leerá `render.yaml` y mostrará tres recursos: `agrotec-kelly-web`, `agrotec-kelly-api` y `agrotec-kelly-db`.
4. Revisa que los planes sean `0.5c-512mb`, `0.5c-512mb` y PostgreSQL `0.1c-256mb`. Son planes pagados y no se duermen.
5. Render solicitará los valores secretos del administrador:
   - `AGROTEC_ADMIN_EMAIL`
   - `AGROTEC_ADMIN_PASSWORD` (mínimo 12 caracteres, única y aleatoria)
   - `AGROTEC_ADMIN_NAME`
6. No cambies `AGROTEC_SESSION_SECRET`: Render lo genera y almacena automáticamente.
7. Crea el Blueprint sólo cuando autorices el costo. Render proporcionará HTTPS automáticamente para la URL `https://agrotec-kelly-web-....onrender.com`.

## 3. Migrar la base SQLite existente

Hazlo antes de entregar la URL a vendedores y mientras nadie esté capturando cambios:

1. En PostgreSQL, abre **Connect** y copia temporalmente la URL externa.
2. Añade temporalmente tu IP a la lista de acceso externo de PostgreSQL.
3. Desde este proyecto y con el entorno virtual activo ejecuta:

   `python backend/scripts/migrate_sqlite_to_postgres.py --source backend/agrotec.db --target-url "URL_EXTERNA_DE_RENDER"`

4. El comando crea primero `backend/backups/agrotec-pre-postgresql-FECHA.db`, verifica su integridad, aplica las migraciones y copia con `upsert` idempotente productos, reglas, ajustes y preferencias.
5. Repite con `--verify-only`. Todas las tablas deben mostrar `matches: true` y productos `283`.
6. Retira inmediatamente tu IP de la lista externa. La base debe volver a `ipAllowList: []`.
7. En Render abre PostgreSQL → **Recovery → Create export** y descarga el primer respaldo lógico posterior a la migración.

## 4. Validación posterior

1. Abre la URL HTTPS del frontend e inicia sesión como administrador.
2. Crea un usuario vendedor en **Usuarios**.
3. En una computadora entra como administrador y en un teléfono entra como vendedor.
4. Comprueba 283 implementos, Tipo Sur 16, LIGHT 10 y las reglas 57.5% → 3% → 10%.
5. Cambia temporalmente el tercer descuento en el teléfono: no debe aparecer como cambio permanente en la computadora.
6. Como administrador, guarda una regla después de su vista previa y verifica que el teléfono la reciba al volver a seleccionar el producto.
7. Prueba `/health` desde el navegador. Render también lo usa para validar frontend, backend y conexión PostgreSQL.
8. Reinicia ambos servicios desde Render y repite inicio de sesión y una cotización.

## 5. Respaldo y restauración

- PostgreSQL pagado mantiene recuperación continua PITR. Revisa periódicamente la página **Recovery**.
- Crea y descarga además una exportación lógica mensual y antes de cada cambio comercial masivo.
- Para probar restauración, usa PITR para crear una base nueva, nunca sobre la base productiva. Valida allí 283 productos y los conteos de reglas/preferencias; después elimina la instancia de prueba.
- Para un export descargado, restaura únicamente en una base vacía con `pg_restore`; no uses `--clean` contra producción.

## 6. Operación segura

- Cada persona debe tener su propia cuenta.
- Desactiva inmediatamente cuentas que ya no deban acceder.
- Los cambios de contraseña o rol cierran las sesiones del usuario.
- Revisa los logs de Render ante respuestas 5xx. Los logs incluyen identificador de solicitud, ruta, estado y duración, pero no contraseñas ni cookies.
- No añadas secretos con prefijo `NEXT_PUBLIC_`; éstos quedarían incluidos en el JavaScript del navegador.
