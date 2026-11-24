"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { getProducts, request } from "@/lib/api";
import { mxn } from "@/lib/format";
import { FamilySummary, Product, Rule } from "@/lib/types";
import DiscountStages from "@/components/DiscountStages";
import { freshKellyDiscounts } from "@/lib/discount-policy";
import { areDiscountsValid } from "@/lib/quote-calculation";

type PreviewItem = { id: string; name: string; list_price_mxn: string; preview_distributor_cost: string; current_rule_origin: "family" | "product" | null };
type Preview = { scope_type: "family" | "products"; scope_key: string | null; affected_count: number; items: PreviewItem[] };

export default function Configuration() {
  const [products, setProducts] = useState<Product[]>([]);
  const [families, setFamilies] = useState<FamilySummary[]>([]);
  const [rules, setRules] = useState<Rule[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [search, setSearch] = useState("");
  const [familyFilter, setFamilyFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "configured" | "pending">("all");
  const [targetFamily, setTargetFamily] = useState("");
  const [discountStages, setDiscountStages] = useState<string[]>(freshKellyDiscounts);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [markup, setMarkup] = useState("25");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const deepLinkApplied = useRef(false);

  async function load() {
    const [catalog, familyData, savedRules, settings] = await Promise.all([
      getProducts("page_size=300&sort=name"), request<{ items: FamilySummary[] }>("/api/families"),
      request<{ items: Rule[] }>("/api/rules"), request<{ default_markup_pct: string }>("/api/settings"),
    ]);
    setProducts(catalog.items); setFamilies(familyData.items); setRules(savedRules.items); setMarkup(settings.default_markup_pct);
  }
  useEffect(() => { load().catch(err => setError(err.message)); }, []);
  useEffect(() => {
    if (!products.length || deepLinkApplied.current) return;
    const params = new URLSearchParams(window.location.search);
    const familyName = params.get("family");
    if (familyName && !families.length) return;
    const third = params.get("third") || "10";
    const staged = ["57.5", "3", third];
    if (areDiscountsValid(staged)) setDiscountStages(staged);
    const productId = params.get("product");
    if (productId && products.some(item => item.id === productId)) setSelected([productId]);
    if (familyName && families.some(item => item.name === familyName)) { setTargetFamily(familyName); setFamilyFilter(familyName); }
    deepLinkApplied.current = true;
  }, [products, families]);

  const visible = useMemo(() => products.filter(item => {
    const matchesSearch = `${item.name} ${item.id} ${item.supplier_code || ""} ${item.family || ""}`.toLowerCase().includes(search.toLowerCase());
    const matchesFamily = !familyFilter || item.family === familyFilter;
    const matchesStatus = statusFilter === "all" || item.status === statusFilter;
    return matchesSearch && matchesFamily && matchesStatus;
  }), [products, search, familyFilter, statusFilter]);

  const discounts = () => discountStages.map(value => value.trim()).filter(Boolean);
  function invalidatePreview() { setPreview(null); }
  function choose(id: string) { setSelected(items => items.includes(id) ? items.filter(item => item !== id) : [...items, id]); invalidatePreview(); }
  function notify(text: string) { setMessage(text); setError(""); setTimeout(() => setMessage(""), 2600); }
  function selectVisible() { setSelected(visible.map(item => item.id)); invalidatePreview(); }

  async function assignFamily() {
    if (!selected.length) return setError("Selecciona al menos un implemento.");
    try {
      await request("/api/products/bulk-family", { method: "POST", body: JSON.stringify({ product_ids: selected, family: targetFamily || null }) });
      notify(`Familia actualizada en ${selected.length} implemento(s).`); setSelected([]); await load();
    } catch (err) { setError(err instanceof Error ? err.message : "No se pudo asignar la familia."); }
  }

  async function previewRule(scope: "products" | "family") {
    if (scope === "products" && !selected.length) return setError("Selecciona al menos un implemento.");
    if (scope === "family" && !targetFamily) return setError("Selecciona la familia que recibirá la regla.");
    try {
      const response = await request<Preview>("/api/rules/preview", {
        method: "POST",
        body: JSON.stringify({
          scope_type: scope, scope_key: scope === "family" ? targetFamily : null,
          product_ids: scope === "products" ? selected : [],
          rule: { discounts: discounts(), explicit_zero: false },
        }),
      });
      setPreview(response); setError("");
    } catch (err) { setError(err instanceof Error ? err.message : "No se pudo generar la vista previa."); }
  }

  async function confirmRule() {
    if (!preview) return setError("Genera la vista previa antes de aplicar.");
    const rule = { discounts: discounts(), explicit_zero: false, name: preview.scope_type === "family" ? `Regla de ${preview.scope_key}` : "Regla individual" };
    try {
      if (preview.scope_type === "family") {
        await request("/api/rules", { method: "PUT", body: JSON.stringify({ scope_type: "family", scope_key: preview.scope_key, rule }) });
      } else {
        await request("/api/rules/bulk-products", { method: "POST", body: JSON.stringify({ product_ids: preview.items.map(item => item.id), rule }) });
      }
      notify(`Regla confirmada para ${preview.affected_count} implemento(s).`); setPreview(null); setSelected([]); await load();
    } catch (err) { setError(err instanceof Error ? err.message : "No se pudo aplicar la regla."); }
  }

  async function saveMarkup() {
    try { await request("/api/settings", { method: "PATCH", body: JSON.stringify({ default_markup_pct: markup }) }); notify("Recargo predeterminado guardado."); }
    catch (err) { setError(err instanceof Error ? err.message : "No se pudo guardar."); }
  }

  return <main className="page-shell config-page">
    <section className="hero compact"><div><p className="eyebrow">Administración local</p><h1>Configuración comercial</h1><p>Clasifica implementos y administra reglas verificadas sin modificar el catálogo fuente.</p></div></section>
    <div className="admin-safety"><strong>Cambios permanentes</strong><span>Esta sección está separada del cotizador. Toda regla requiere vista previa y confirmación antes de guardarse.</span></div>
    {message && <div className="alert success">{message}</div>}{error && <div className="alert error">{error}</div>}

    <div className="config-grid">
      <section className="settings-card"><h2>Ganancia predeterminada</h2><p>Recargo sobre costo usado cuando el producto no tiene preferencia propia.</p><label><span>Recargo</span><div className="input-suffix"><input type="number" min="0" value={markup} onChange={e => setMarkup(e.target.value)} /><b>%</b></div></label><button onClick={saveMarkup}>Guardar valor</button><p className="hint">Cada producto puede guardar porcentaje, utilidad fija y redondeo propios.</p></section>
      <section className="settings-card"><h2>Reglas existentes</h2><div className="rule-list">{rules.map(rule => <div key={rule.id}><span className={`scope ${rule.scope_type}`}>{rule.scope_type === "family" ? "Familia" : "Producto"}</span><strong>{rule.scope_key}</strong><small>{rule.discounts.map(value => `${value}%`).join(" → ")}</small></div>)}</div></section>
    </div>

    <section className="admin-card">
      <div className="admin-heading"><div><h2>Edición individual y masiva</h2><p>Filtra, selecciona y revisa el impacto antes de confirmar cualquier descuento.</p></div><strong>{selected.length} seleccionados</strong></div>
      <div className="filter-grid">
        <label><span>Buscar</span><input value={search} onChange={e => setSearch(e.target.value)} placeholder="Modelo o ID…" /></label>
        <label><span>Filtrar familia</span><select value={familyFilter} onChange={e => setFamilyFilter(e.target.value)}><option value="">Todas las familias</option>{families.map(item => <option key={item.name} value={item.name}>{item.name} ({item.count})</option>)}</select></label>
        <label><span>Estado descuento</span><select value={statusFilter} onChange={e => setStatusFilter(e.target.value as typeof statusFilter)}><option value="all">Todos</option><option value="configured">Configurados</option><option value="pending">Pendientes</option></select></label>
        <button className="secondary" onClick={selectVisible}>Seleccionar {visible.length} visibles</button>
      </div>
      <div className="family-assignment"><label><span>Familia de destino</span><select value={targetFamily} onChange={e => { setTargetFamily(e.target.value); invalidatePreview(); }}><option value="">Familia por confirmar</option>{families.filter(item => item.status !== "needs_confirmation").map(item => <option key={item.name} value={item.name}>{item.name}</option>)}</select></label><button className="secondary" onClick={assignFamily}>Asignar familia a seleccionados</button></div>

      <p className="selection-summary"><strong>{visible.length}</strong> visibles · <strong>{selected.length}</strong> seleccionados</p>
      <div className="selection-list">{visible.map(product => <label key={product.id} className={selected.includes(product.id) ? "selected" : ""}>
        <input type="checkbox" checked={selected.includes(product.id)} onChange={() => choose(product.id)} />
        <span><strong>{product.name}</strong><small>{product.id} · {product.family}</small></span>
        <span className="rule-origin">{product.rule ? (product.rule.scope_type === "product" ? "Regla individual" : "Regla familiar") : "Sin regla"}</span>
        <em className={`badge ${product.status}`}>{product.status === "configured" ? "Configurado" : "Pendiente"}</em>
      </label>)}</div>

      <div className="rule-editor enhanced">
        <div><span className="field-label">Política de descuentos Kelly (%)</span><DiscountStages values={discountStages} onChange={values => { setDiscountStages(values); invalidatePreview(); }} lockedCount={2} allowStructureChanges={false} /><small>57.5% y 3% están bloqueados. Sólo el tercer descuento es editable y acepta decimales o 0%.</small></div>
        <div className="policy-note"><strong>Tercer descuento vigente</strong><span>{discountStages[2] || "—"}%</span></div>
        <div className="rule-buttons"><button onClick={() => previewRule("products")}>Previsualizar seleccionados</button><button className="secondary" onClick={() => previewRule("family")}>Previsualizar familia</button></div>
      </div>

      {preview && <div className="preview-panel"><div><h3>Vista previa antes de confirmar</h3><p>{preview.scope_type === "family" ? `Regla familiar: ${preview.scope_key}` : "Sobrescritura individual"} · <strong>{preview.affected_count} productos serán modificados</strong></p></div><div className="preview-table">{preview.items.map(item => <div key={item.id}><span><strong>{item.name}</strong><small>{item.id} · Regla actual: {item.current_rule_origin === "product" ? "individual" : item.current_rule_origin === "family" ? "familiar" : "ninguna"}</small></span><span>{mxn(item.list_price_mxn)} → costo <b>{mxn(item.preview_distributor_cost)}</b></span></div>)}</div><button onClick={confirmRule}>Confirmar cambios en {preview.affected_count} implemento(s)</button></div>}
    </section>
  </main>;
}
