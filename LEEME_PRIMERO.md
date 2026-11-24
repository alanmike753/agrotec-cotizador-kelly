# Agrotec de Occidente — MVP de lista de precios Kelly (solo IMPLEMENTOS)

## Qué contiene

- `data/implementos_kelly_enero_2026.json`: catálogo normalizado de **283 implementos**.
- `data/implementos_kelly_enero_2026.csv`: versión tabular del catálogo.
- `data/lista 70 Enero 2026 (2).xlsx`: fuente original SOLO PARA CONSULTA; el programa debe leer únicamente la pestaña **Implementos**.
- `assets/logo_agrotec_referencia.png`: imagen de referencia, confirmar que corresponde a la versión del logo elegida por Agrotec.
- `PROMPT_PARA_CODEX_SOLO_IMPLEMENTOS.md`: instrucciones precisas para desarrollar la primera versión en Codex.

## Cómo iniciar en Codex

1. Extrae el ZIP en una carpeta nueva (por ejemplo `C:\cotizador-agrotec-implementos`).
2. Abre esa carpeta en Codex o VS Code con Codex.
3. Abre `PROMPT_PARA_CODEX_SOLO_IMPLEMENTOS.md` y pega todo su contenido como instrucción inicial.
4. Pide a Codex que implemente y pruebe la primera etapa, sin añadir discos, refacciones ni PDFs.

## Reglas de negocio confirmadas

- Sólo las 22 rastras de levante tipo V poseen descuentos confirmados: **-57%**, después **-3%**, después **-10%**.
- Los otros 261 productos tienen descuento **pendiente**.
- La ganancia sugerida inicial es **25% de recargo sobre costo**, editable por implemento.
- Precios de lista en pesos mexicanos; IVA por confirmar.

**Fuente del logo de referencia:** https://dealers.argotractors.com/mx/dealer/agrotec/
