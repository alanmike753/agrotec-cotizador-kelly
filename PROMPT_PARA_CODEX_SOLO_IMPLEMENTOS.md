# INSTRUCCIONES PARA CODEX — AGROTEC DE OCCIDENTE
## MVP 1: lista de precios de IMPLEMENTOS KELLY (sin discos ni refacciones)

Quiero que desarrolles una aplicación web interna, responsiva y funcional, de **Agrotec de Occidente** para consultar y calcular precios de implementos agrícolas Kelly. En esta primera etapa únicamente trabajarás con los productos incluidos en la pestaña **Implementos** del archivo fuente y el JSON normalizado `data/implementos_kelly_enero_2026.json`.

**Restricción primordial de alcance:** NO importar, mostrar, administrar ni cotizar ningún producto de las pestañas «Discos» y «Refacciones». NO construir todavía facturación, inventario, CRM, gestión de clientes ni el módulo completo de PDF de cotizaciones. Esta etapa se concentra en la lista interna de precios y en obtener rápidamente un precio de venta propuesto por producto. Diseñar el proyecto de forma extensible para agregar cotizaciones en una siguiente etapa, pero no implementarlas ahora.

### Los datos ya preparados

- 283 implementos de la **Lista de precios No. 70, enero 2026**.
- Documento de origen: `data/lista 70 Enero 2026 (2).xlsx` (leer **solo** la pestaña Implementos para verificaciones). Proveedor que aparece en el documento: **Industrias Cabrera, S.A. de C.V.**; el nombre comercial que usará la aplicación será Kelly según el negocio. No sustituir el nombre del proveedor en los metadatos.
- Carga inicial: `data/implementos_kelly_enero_2026.json`; contiene **283** productos con ID estable, modelo, precio lista, origen en Excel y estado de descuento.
- CSV alternativo: `data/implementos_kelly_enero_2026.csv`.
- **22** rastras de levante tipo V ya tienen regla comercial confirmada: **57%, 3%, 10% consecutivos**.
- Los otros **261** implementos **NO** tienen descuento verificado. Deben mostrarse **«Pendiente de configurar»**. Nunca asignar automáticamente descuento cero o copiar la regla de las rastras.

### Flujo principal de vendedor

1. Abrir la app y ver la sección «Lista de precios de implementos».
2. Buscar por modelo/nombre, filtrar por familia cuando se haya definido y ver un listado ordenable.
3. Abrir un implemento y ver su **precio de lista**, descuentos escalonados (cuando existan), **costo distribuidor** calculado y **precio público propuesto**.
4. Ajustar una **ganancia individual** de ese implemento: porcentaje de recargo sobre costo o utilidad fija por unidad. Preconfigurar 25% como valor **propuesto y editable**, no como impuesto ni descuento.
5. Elegir redondeo comercial (peso entero por defecto; opcional $10, $50, $100 hacia arriba) y ver inmediatamente el nuevo precio y utilidad. Poder copiar el resumen del producto o imprimir una ficha interna sencilla desde el navegador. Nada de PDFs complejos en esta fase.
6. Si falta descuento del implemento, la aplicación debe mostrar su precio lista y el estado pendiente, y **no** inventar costo distribuidor, utilidad ni precio público. Un administrador puede introducir los descuentos correctos de ese artículo o su familia y recién entonces habilitar el cálculo.

### Administración de reglas

- Descuentos **sucesivos y en orden**, con cualquier número de escalones: `precio_lista × (1-d1/100) × (1-d2/100) × ...`.
- Permitir reglas por **familia** y sobreescritura por **producto**. No deducir familias no confirmadas a ciegas: el campo de familia que viene vacío se podrá editar y asignar por lotes desde la interfaz.
- Edición individual y masiva de descuentos. Mostrar vista previa antes de aplicar una regla a muchos modelos.
- Mantener origen de cada precio (hoja, fila, columna) y marca de fecha de la actualización.
- Guardar cambios de descuentos/ganancias predeterminadas localmente en SQLite, sin modificar el JSON fuente.
- Distinguir «sin regla» de «regla explícita de 0%»: la segunda solo puede aplicarse si un usuario autorizado la decide.

### Cálculos exactos

1. Costo distribuidor = precio de lista tras aplicar **uno a uno** los descuentos, redondeado a 2 decimales usando `Decimal` y `ROUND_HALF_UP`.
2. Recargo sobre costo (markup) = `costo_distribuidor * (1 + porcentaje/100)`. Ganancia fija = `costo_distribuidor + ganancia_en_pesos`.
3. Precio de venta sugerido redondeado comercialmente (al peso entero con `ROUND_HALF_UP` por defecto, pero configurable).
4. Mostrar recargo, costo, utilidad en pesos y margen bruto real sobre venta, para que recargo y margen no se confundan.
5. IVA: **no incluir automáticamente**; el documento no especifica si los precios lo contienen. Mostrar advertencia «IVA por confirmar» donde corresponda, pero no sumar impuestos no autorizados.
6. No usar `float` para operaciones monetarias.

**Casos de prueba obligatorios:**
- Rastra sin limpiadores `implementos-0089-I`, RL-14 24 X 5/32, precio lista $82,278 → costo con -57%, -3%, -10% = **$30,886.34** → venta con recargo 25%, redondeo a peso = **$38,608**.
- Rastra con limpiadores `implementos-0103-I`, RL-14 24 X 5/32, precio lista $90,780 → costo **$34,077.90** → venta **$42,597**.
- Validar 283 implementos importados, 22 reglas asignadas, 261 pendientes, 0 productos de Discos/Refacciones; importaciones repetidas no duplican registros.
- Probar descuentos sucesivos, varios tipos de redondeo, estado sin regla, cambios de ganancia y actualización de reglas.

### Interfaz

- Diseño profesional en español, fácil de usar en desktop y móvil, identidad verde/dorado/crema de Agrotec.
- Encabezado con el logo `assets/logo_agrotec_referencia.png` si está presente; marcarlo como **referencia a confirmar** antes de publicar como identidad definitiva.
- Vista de **tabla**, búsqueda instantánea, filtros de «Configurado / Pendiente» y detalles por implemento. Mostrar 283 en total; no usar imágenes inventadas de productos.
- Pantalla sencilla de **Configuración** para reglas de descuentos y valor predeterminado de ganancia 25%.
- Mostrar todos los importes en MXN con separador de miles.

### Stack sugerido

- Next.js (App Router) + TypeScript + Tailwind CSS para frontend.
- FastAPI + Pydantic + SQLAlchemy + SQLite para backend y persistencia; Alembic para migraciones si resulta práctico.
- `Decimal` en Python para cálculo monetario. Los importes deben serializarse como **cadenas decimales** en API; no convertirse silenciosamente a `float`.
- Pruebas automatizadas `pytest` y las de frontend necesarias.
- Sin pagos, WhatsApp, correo, despliegue público ni autenticación compleja en este MVP local. Si la app se publica más adelante habrá que incorporar acceso seguro y roles; no declararla lista para internet ahora.

### Orden de trabajo que quiero que sigas

1. **Inspecciona** JSON, CSV, pestaña Implementos del XLSX y los 22 IDs con descuentos. Define un plan breve y esquema de base de datos.
2. Implementa primero la importación y el **motor de descuentos**, con pruebas.
3. Implementa luego la pantalla de lista, buscador, ficha de producto y **ganancia configurable**, con tests de interfaz.
4. Implementa administración de descuentos por producto/familia, persistencia y estado pendiente.
5. Ejecuta pruebas reales y muestra resultados, errores corregidos y comandos exactos de inicio en **Windows PowerShell**. No reportes pruebas que no ejecutaste.
6. Detente al completar este alcance: **no avances a módulo de cotizaciones en PDF ni a otras pestañas del Excel** sin mi autorización.

**Resultado deseado:** un vendedor selecciona cualquiera de los 283 implementos y puede ver en segundos su costo distribuidor y su precio público sugerido, siempre que se hayan configurado sus descuentos de forma verificable. El sistema permite proponer ganancias diferentes por producto.
