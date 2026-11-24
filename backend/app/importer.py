from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import DiscountRule, Product, Setting


ROOT_DIR = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT_DIR / "data" / "implementos_kelly_enero_2026.json"
CONFIRMED_RULE = ["57.5", "3", "10"]


def import_catalog(db: Session, catalog_path: Path = CATALOG_PATH) -> dict[str, int]:
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    products = payload["productos"]
    seen_ids: set[str] = set()
    for item in products:
        if item["id"] in seen_ids:
            raise ValueError(f"ID duplicado en catálogo: {item['id']}")
        seen_ids.add(item["id"])
        if item["categoria_general"] != "Implementos" or item["origen"]["hoja"] != "Implementos":
            raise ValueError(f"Producto fuera de alcance: {item['id']}")
        product = db.get(Product, item["id"])
        is_new = product is None
        if is_new:
            product = Product(id=item["id"])
            db.add(product)
        product.name = item["nombre"]
        product.supplier_code = item.get("codigo_proveedor")
        product.category = item["categoria_general"]
        # Preserve locally edited families on repeat imports.
        if is_new:
            product.family = item.get("familia_comercial")
        product.list_price = str(item["precio_lista_mxn"])
        product.source_sheet = item["origen"]["hoja"]
        product.source_row = int(item["origen"]["fila"])
        product.source_model_column = item["origen"]["columna_modelo"]
        product.source_price_column = item["origen"]["columna_precio"]
        product.source_rule_code = item.get("regla_descuento_codigo")

    configured_families = sorted({
        item["familia_comercial"]
        for item in products
        if item.get("regla_descuento_codigo") == "rastra_tipo_v_57_3_10"
    })
    for family in configured_families:
        existing = db.scalar(select(DiscountRule).where(
            DiscountRule.scope_type == "family", DiscountRule.scope_key == family
        ))
        if existing is None:
            db.add(DiscountRule(
                scope_type="family",
                scope_key=family,
                name="Rastras levante tipo V — regla confirmada",
                discounts_json=json.dumps(CONFIRMED_RULE),
                explicit_zero=False,
                source="Confirmado en Lista No. 70 / conversación",
            ))
    if db.get(Setting, "default_markup_pct") is None:
        db.add(Setting(key="default_markup_pct", value="25"))
    db.commit()
    total = db.query(Product).count()
    return {"source_products": len(products), "database_products": total}

