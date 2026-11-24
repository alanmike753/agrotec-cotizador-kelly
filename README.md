# Agrotec de Occidente — lista interna de precios Kelly

MVP local para consultar exclusivamente los 283 productos de la hoja **Implementos** de la Lista No. 70 (enero de 2026). No importa ni muestra las hojas Discos o Refacciones.

## Requisitos

- Python 3.12 o compatible
- Node.js 20.9 o posterior (probado con Node 24)
- Windows PowerShell

## Primera instalación

Desde la raíz del proyecto, en PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
Set-Location .\frontend
npm install
Set-Location ..
```

## Iniciar la aplicación

Abre dos ventanas de PowerShell en la raíz del proyecto.

Antes del primer arranque define las variables de `backend/.env.example`, en especial
`AGROTEC_ADMIN_EMAIL`, `AGROTEC_ADMIN_PASSWORD` y `AGROTEC_SESSION_SECRET`.

Backend:

```powershell
Set-Location .\backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
Set-Location .\frontend
npm run dev
```

Luego abre [http://127.0.0.1:3000](http://127.0.0.1:3000). La base local se crea en `backend/agrotec.db`; el JSON fuente no se modifica.

El arranque aplica migraciones versionadas y crea una copia íntegra en `backend/backups` antes de cualquier cambio pendiente. La política Kelly usa descuentos sucesivos de 57.5% y 3% fijos, más un tercer descuento editable (10% predeterminado). Las preferencias por producto conservan porcentaje o utilidad fija, redondeo y fecha de actualización; la clasificación familiar permanece separada de las reglas de descuento.

## Pruebas y compilación

```powershell
Set-Location .\backend
..\.venv\Scripts\python.exe -m pytest -q

Set-Location ..\frontend
npm test
npm run build
npm audit
```

## Alcance y seguridad

- Solo Implementos Kelly; 283 productos auditados contra la hoja `Implementos` y clasificados en 30 familias comerciales.
- Los productos sin tercer descuento guardado se calculan con 10% temporal sin modificar SQLite.
- IVA no incluido: permanece “por confirmar”.
- El logo incluido es una referencia que debe confirmarse antes de publicar.
- El acceso requiere sesión individual; los endpoints permanentes exigen rol administrador.
- Producción usa PostgreSQL y servicios pagados sin suspensión. Consulta `DEPLOY_RENDER.md` y `render.yaml`.

