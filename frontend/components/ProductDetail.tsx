"use client";

import { useEffect, useState } from "react";
import { calculateProduct, getProduct, request } from "@/lib/api";
import { mxn, shortDate } from "@/lib/format";
import { Calculation, Product } from "@/lib/types";

type Mode = "markup" | "fixed";
type Rounding = "1" | "10" | "50" | "100";

export default function ProductDetail({ productId, onClose, onChanged }: { productId: string; onClose: () => void; onChanged: () => void }) {
  const [product, setProduct] = useState<Product | null>(null);
  const [calculation, setCalculation] = useState<Calculation | null>(null);
  const [mode, setMode] = useState<Mode>("markup");
  const [profit, setProfit] = useState("25");
  const [rounding, setRounding] = useState<Rounding>("1");
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    getProduct(productId).then(item => {
      setProduct(item);
      setCalculation(item.calculation);
      setMode(item.commercial_preference.profit_mode);
      setProfit(item.commercial_preference.profit_value);
      setRounding(item.commercial_preference.rounding_increment);
    }).catch(err => setError(err.message));
  }, [productId]);

  useEffect(() => {
    if (!product?.rule) return;
    const timer = setTimeout(() => {
      calculateProduct(product.id, { profit_mode: mode, profit_value: profit || "0", rounding_increment: rounding })
        .then(value => { setCalculation(value as Calculation); setError(""); })
        .catch(err => setError(err.message));
    }, 150);
    return () => clearTimeout(timer);
  }, [product, mode, profit, rounding]);

  function summary() {
    if (!product || !calculation) return "";
    return `${product.name} (${product.id})\nPrecio lista: ${mxn(product.list_price_mxn)}\nDescuentos: ${product.rule?.discounts.map(v => `${v}%`).join(" → ")}\nCosto distribuidor: ${mxn(calculation.distributor_cost)}\nPrecio sugerido: ${mxn(calculation.suggested_price)}\nUtilidad: ${mxn(calculation.profit_amount)}\nIVA por confirmar.`;
  }

  async function copy() {
    await navigator.clipboard.writeText(summary());
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  }

  async function savePreference() {
    if (!product) return;
    try {
      const updated = await request<Product>(
        `/api/products/${encodeURIComponent(product.id)}/commercial-preference`,
        { method: "PUT", body: JSON.stringify({ profit_mode: mode, profit_value: profit, rounding_increment: rounding }) },
      );
      setProduct(updated);
      setCalculation(updated.calculation);
      setSaved(true);
      onChanged();
      setTimeout(() => setSaved(false), 1400);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo guardar la configuración comercial.");
    }
  }

  return <div className="drawer-backdrop" onMouseDown={event => event.target === event.currentTarget && onClose()}>
    <aside className="drawer" aria-label="Detalle del implemento">
      <button className="close" onClick={onClose} aria-label="Cerrar">×</button>
      {!product ? <p>Cargando…</p> : <>
        <p className="eyebrow">{product.id}</p><h2>{product.name}</h2>
        <p className="family-line">{product.family}{product.family_status === "needs_confirmation" && <span className="family-review"> · Requiere autorización</span>}</p>
        <div className="price-block"><span>Precio de lista</span><strong>{mxn(product.list_price_mxn)}</strong><small>MXN · IVA por confirmar</small></div>

        {product.rule ? <section className="rule-strip">
          <span>Descuentos sucesivos</span><strong>{product.rule.discounts.map(value => `−${value}%`).join("  →  ")}</strong>
          <small>{product.rule.scope_type === "product" ? "Regla individual" : "Regla familiar"} · {product.rule.source}</small>
        </section> : <div className="pending-panel">
          <span className="badge pending">Pendiente de configurar</span><h3>No hay descuento verificado</h3>
          <p>El costo distribuidor, la utilidad y el precio público permanecen bloqueados hasta que un administrador configure una regla.</p><a href="/configuracion">Ir a configuración</a>
        </div>}

        <section className="calculator">
          <h3>Preferencia comercial del producto</h3>
          <div className="segmented"><button className={mode === "markup" ? "active" : ""} onClick={() => setMode("markup")}>Recargo %</button><button className={mode === "fixed" ? "active" : ""} onClick={() => setMode("fixed")}>Utilidad fija</button></div>
          <div className="form-grid">
            <label><span>{mode === "markup" ? "Recargo sobre costo" : "Utilidad por unidad"}</span><div className="input-suffix"><input type="number" min="0" step="0.01" value={profit} onChange={e => setProfit(e.target.value)} /><b>{mode === "markup" ? "%" : "MXN"}</b></div></label>
            <label><span>Redondeo comercial</span><select value={rounding} onChange={e => setRounding(e.target.value as Rounding)}><option value="1">Peso entero</option><option value="10">$10 hacia arriba</option><option value="50">$50 hacia arriba</option><option value="100">$100 hacia arriba</option></select></label>
          </div>
          <button className="save-preference" onClick={savePreference}>{saved ? "Configuración guardada" : "Guardar para este producto"}</button>
          {product.commercial_preference.updated_at && <small className="saved-at">Última actualización: {shortDate(product.commercial_preference.updated_at)}</small>}
        </section>

        {calculation && <section className="result-card"><div><span>Costo distribuidor</span><strong>{mxn(calculation.distributor_cost)}</strong></div><div className="featured"><span>Precio público propuesto</span><strong>{mxn(calculation.suggested_price)}</strong></div><div><span>Utilidad en pesos</span><strong>{mxn(calculation.profit_amount)}</strong></div><div><span>Recargo efectivo</span><strong>{calculation.effective_markup_pct}%</strong></div><div><span>Margen bruto real</span><strong>{calculation.gross_margin_pct}%</strong></div></section>}
        {error && <div className="alert error">{error}</div>}
        {calculation && <div className="detail-actions"><button onClick={copy}>{copied ? "Copiado" : "Copiar resumen"}</button><button className="secondary" onClick={() => window.print()}>Imprimir ficha</button></div>}
        <details><summary>Origen y trazabilidad</summary><p>Hoja {product.origin.sheet}, fila {product.origin.row}, columnas {product.origin.model_column}/{product.origin.price_column}.</p><p>Encabezado fuente: {product.family_source_label}</p><p>Catálogo actualizado: {shortDate(product.origin.updated_at)}</p><p>Proveedor del documento: Industrias Cabrera, S.A. de C.V.</p></details>
      </>}
    </aside>
  </div>;
}
