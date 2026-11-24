"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import DiscountStages from "@/components/DiscountStages";
import { calculateProduct, getProduct, getProducts, request } from "@/lib/api";
import { mxn } from "@/lib/format";
import { buildClientQuote } from "@/lib/quote";
import { areDiscountsValid, buildCalculationPayload, usesTemporaryDiscounts } from "@/lib/quote-calculation";
import { freshKellyDiscounts } from "@/lib/discount-policy";
import { Calculation, FamilySummary, Product } from "@/lib/types";
import { useAuth } from "@/components/AppShell";

export default function Home() {
  const { user } = useAuth();
  const isAdmin = user.role === "admin";
  const [catalog, setCatalog] = useState<Product[]>([]);
  const [families, setFamilies] = useState<FamilySummary[]>([]);
  const [selected, setSelected] = useState<Product | null>(null);
  const [search, setSearch] = useState("");
  const [family, setFamily] = useState("");
  const [discounts, setDiscounts] = useState<string[]>(freshKellyDiscounts);
  const [profitMode, setProfitMode] = useState<"markup" | "fixed">("markup");
  const [profitValue, setProfitValue] = useState("25");
  const [rounding, setRounding] = useState<"1" | "10" | "50" | "100">("1");
  const [calculation, setCalculation] = useState<Calculation | null>(null);
  const [loading, setLoading] = useState(true);
  const [calculating, setCalculating] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const requestNumber = useRef(0);
  const selectionNumber = useRef(0);

  useEffect(() => {
    Promise.all([
      getProducts("page_size=300&sort=name"),
      request<{ items: FamilySummary[] }>("/api/families"),
    ]).then(([products, familyData]) => {
      setCatalog(products.items);
      setFamilies(familyData.items);
      const first = products.items.find(item => item.status === "configured") || products.items[0];
      if (first) selectProduct(first.id);
    }).catch(err => setError(err instanceof Error ? err.message : "No se pudo cargar el catálogo."))
      .finally(() => setLoading(false));
  }, []);

  async function selectProduct(id: string) {
    const currentSelection = ++selectionNumber.current;
    ++requestNumber.current;
    setError(""); setCalculation(null); setCalculating(false); setSelected(null); setDiscounts(freshKellyDiscounts());
    try {
      const product = await getProduct(id);
      if (currentSelection !== selectionNumber.current) return;
      setSelected(product);
      setDiscounts(product.rule?.discounts || freshKellyDiscounts());
      setProfitMode(product.commercial_preference.profit_mode);
      setProfitValue(product.commercial_preference.profit_value);
      setRounding(product.commercial_preference.rounding_increment);
    } catch (err) {
      if (currentSelection === selectionNumber.current) setError(err instanceof Error ? err.message : "No se pudo abrir el implemento.");
    }
  }

  const visible = useMemo(() => {
    const needle = search.trim().toLocaleLowerCase("es-MX");
    return catalog.filter(item => {
      const haystack = `${item.name} ${item.id} ${item.supplier_code || ""} ${item.family || ""}`.toLocaleLowerCase("es-MX");
      return (!needle || haystack.includes(needle)) && (!family || item.family === family);
    }).slice(0, 80);
  }, [catalog, search, family]);

  const hasValidDiscounts = areDiscountsValid(discounts);
  const discountIsTemporary = selected ? usesTemporaryDiscounts(selected, discounts) : false;
  const savedPreference = selected?.commercial_preference;
  const profitIsTemporary = !!savedPreference && (
    savedPreference.profit_mode !== profitMode || Number(savedPreference.profit_value) !== Number(profitValue) || savedPreference.rounding_increment !== rounding
  );

  useEffect(() => {
    const current = ++requestNumber.current;
    if (!selected || !hasValidDiscounts || profitValue === "" || Number(profitValue) < 0) {
      setCalculation(null); setCalculating(false); return;
    }
    setCalculating(true); setError("");
    const timer = setTimeout(() => {
      const payload = buildCalculationPayload(selected, discounts, profitMode, profitValue, rounding);
      calculateProduct(selected.id, payload).then(result => { if (current === requestNumber.current) setCalculation(result); })
        .catch(err => { if (current === requestNumber.current) { setCalculation(null); setError(err instanceof Error ? err.message : "No se pudo calcular."); } })
        .finally(() => { if (current === requestNumber.current) setCalculating(false); });
    }, 180);
    return () => clearTimeout(timer);
  }, [selected, discounts, hasValidDiscounts, profitMode, profitValue, rounding]);

  async function savePreference() {
    if (!selected || profitValue === "" || Number(profitValue) < 0) return;
    try {
      const product = await request<Product>(`/api/products/${encodeURIComponent(selected.id)}/commercial-preference`, {
        method: "PUT", body: JSON.stringify({ profit_mode: profitMode, profit_value: profitValue, rounding_increment: rounding }),
      });
      setSelected(product); setNotice("Preferencia comercial guardada para este implemento.");
      setTimeout(() => setNotice(""), 2600);
    } catch (err) { setError(err instanceof Error ? err.message : "No se pudo guardar la preferencia."); }
  }

  async function copyQuote() {
    if (!selected || !calculation) return;
    await navigator.clipboard.writeText(buildClientQuote(selected, calculation));
    setNotice("Precio y datos para el cliente copiados.");
    setTimeout(() => setNotice(""), 2600);
  }

  const originLabel = !selected || !hasValidDiscounts
    ? "Pendiente"
    : discountIsTemporary ? "Simulación temporal"
    : selected.rule?.scope_type === "product" ? "Regla individual guardada" : "Regla familiar guardada";

  return <main className="page-shell quote-page">
    <section className="quote-intro"><div><p className="eyebrow">Cotizador comercial Kelly</p><h1>Cotiza en una sola pantalla</h1><p>Selecciona un implemento, ajusta la operación y comparte únicamente el precio final.</p></div><div className="quote-trust"><strong>283</strong><span>implementos originales</span></div></section>
    {notice && <div className="alert success" role="status">{notice}</div>}{error && <div className="alert error" role="alert">{error}</div>}

    <div className="quote-layout">
      <aside className="product-picker" aria-label="Selector de implementos">
        <div className="picker-heading"><div><span>Paso 1</span><h2>Elige el implemento</h2></div><b>{visible.length}{visible.length < catalog.length ? ` de ${catalog.length}` : ""}</b></div>
        <label className="picker-search"><span>Buscar modelo, familia o descripción</span><input autoFocus value={search} onChange={event => setSearch(event.target.value)} placeholder="Ej. rastra, 2424…" /></label>
        <label><span>Familia</span><select value={family} onChange={event => setFamily(event.target.value)}><option value="">Todas las familias</option>{families.map(item => <option key={item.name} value={item.name}>{item.name} ({item.count})</option>)}</select></label>
        <div className="quick-list">{loading ? <p className="empty">Cargando implementos…</p> : visible.map(product => <button key={product.id} className={selected?.id === product.id ? "active" : ""} onClick={() => selectProduct(product.id)}>
          <span><strong>{product.name}</strong><small>{product.family} · {mxn(product.list_price_mxn)}</small></span><em className={`status-dot ${product.status}`} title={product.status === "configured" ? "Tercer descuento guardado" : "Usa 10% predeterminado"} />
        </button>)}{!loading && !visible.length && <p className="empty">No encontramos implementos con esa búsqueda.</p>}</div>
      </aside>

      <section className="quote-workspace" aria-live="polite">
        {!selected ? <div className="workspace-empty">Selecciona un implemento para comenzar.</div> : <>
          <header className="selected-product"><div><span>{selected.family_status === "needs_confirmation" ? "Familia por confirmar" : selected.family}</span><h2>{selected.name}</h2><small>{selected.supplier_code ? `Código ${selected.supplier_code} · ` : ""}{selected.id}</small></div><div className="list-price"><span>Precio de lista</span><strong>{mxn(selected.list_price_mxn)}</strong></div></header>

          <div className="quote-controls">
            <section className="control-card discounts-card"><div className="section-title"><div><span>Paso 2</span><h3>Descuentos sucesivos</h3></div><em className={discountIsTemporary ? "temporary" : hasValidDiscounts ? "saved" : "pending"}>{originLabel}</em></div>
              {!selected.rule && hasValidDiscounts && <p className="temporary-confirmation">57.5% y 3% son fijos. El tercer descuento usa 10% temporal hasta que decidas guardarlo.</p>}
              <DiscountStages values={discounts} onChange={setDiscounts} compact lockedCount={2} allowStructureChanges={false} />
              {discountIsTemporary && selected.rule && <button className="text-button" onClick={() => setDiscounts(selected.rule?.discounts || freshKellyDiscounts())}>Restaurar tercer descuento guardado</button>}
              {isAdmin && <div className="discount-save-links"><Link href={`/configuracion?product=${encodeURIComponent(selected.id)}&third=${encodeURIComponent(discounts[2] || "10")}`}>Guardar para este producto</Link>{selected.family_status !== "needs_confirmation" && selected.family && <Link href={`/configuracion?family=${encodeURIComponent(selected.family)}&third=${encodeURIComponent(discounts[2] || "10")}`}>Guardar para esta familia</Link>}</div>}
              <p className="control-help">{isAdmin ? "Puedes usar este valor sólo en la cotización actual. Guardarlo abre Administración con vista previa obligatoria." : "Este descuento se aplica sólo a tu cotización actual y no modifica las reglas guardadas."}</p>
            </section>

            <section className="control-card profit-card"><div className="section-title"><div><span>Paso 3</span><h3>Ganancia y redondeo</h3></div><em className={profitIsTemporary ? "temporary" : "saved"}>{profitIsTemporary ? "Temporal" : savedPreference?.is_custom ? "Guardada" : "Predeterminada"}</em></div>
              <div className="segmented"><button className={profitMode === "markup" ? "active" : ""} onClick={() => setProfitMode("markup")}>Recargo %</button><button className={profitMode === "fixed" ? "active" : ""} onClick={() => setProfitMode("fixed")}>Utilidad $</button></div>
              <div className="profit-grid"><label><span>{profitMode === "markup" ? "Recargo sobre costo" : "Utilidad fija"}</span><div className="input-suffix"><input type="number" min="0" step="0.01" value={profitValue} onChange={event => setProfitValue(event.target.value)} /><b>{profitMode === "markup" ? "%" : "$"}</b></div></label><label><span>Redondeo comercial</span><select value={rounding} onChange={event => setRounding(event.target.value as typeof rounding)}><option value="1">$1</option><option value="10">$10</option><option value="50">$50</option><option value="100">$100</option></select></label></div>
              {isAdmin && <button className="save-preference" onClick={savePreference} disabled={!profitIsTemporary}>Guardar como preferencia del implemento</button>}
            </section>
          </div>

          <section className={`sale-result ${!calculation ? "unavailable" : ""}`}>
            <div className="result-main"><span>Precio final de venta</span><strong>{calculating ? "Calculando…" : calculation ? mxn(calculation.suggested_price) : "Pendiente de descuentos"}</strong><small>MXN · IVA por confirmar</small></div>
            <button onClick={copyQuote} disabled={!calculation}>Copiar para el cliente</button>
          </section>

          {calculation && <div className="calculation-details" aria-label="Información interna"><div><span>Costo distribuidor</span><strong>{mxn(calculation.distributor_cost)}</strong></div><div><span>Utilidad estimada</span><strong>{mxn(calculation.profit_amount)}</strong></div><div><span>Recargo efectivo</span><strong>{calculation.effective_markup_pct}%</strong></div><div><span>Margen real</span><strong>{calculation.gross_margin_pct}%</strong></div></div>}

          {calculation && <section className="client-preview"><div><span>Vista que se copia al cliente</span><strong>{selected.name}</strong><small>{selected.family} · MXN · IVA por confirmar</small></div><b>{mxn(calculation.suggested_price)}</b></section>}
        </>}
      </section>
    </div>
  </main>;
}
