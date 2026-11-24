import json
from decimal import Decimal
from pathlib import Path

from openpyxl import load_workbook

from app.family_classifier import NEEDS_CONFIRMATION, classification_for


ROOT = Path(__file__).resolve().parents[2]


def test_json_matches_every_referenced_excel_cell_in_implementos_sheet():
    payload = json.loads((ROOT / "data" / "implementos_kelly_enero_2026.json").read_text(encoding="utf-8"))
    workbook = load_workbook(ROOT / "data" / "lista 70 Enero 2026 (2).xlsx", read_only=True, data_only=True)
    assert workbook.sheetnames == ["Implementos", "Discos", "Refacciones"]
    sheet = workbook["Implementos"]
    assert len(payload["productos"]) == 283
    for product in payload["productos"]:
        origin = product["origen"]
        assert origin["hoja"] == "Implementos"
        model = sheet[f"{origin['columna_modelo']}{origin['fila']}"].value
        price = sheet[f"{origin['columna_precio']}{origin['fila']}"].value
        assert str(model).strip() == product["nombre"].strip()
        assert Decimal(str(price)) == Decimal(product["precio_lista_mxn"])


def test_every_excel_product_has_an_audited_family_across_all_three_blocks():
    payload = json.loads((ROOT / "data" / "implementos_kelly_enero_2026.json").read_text(encoding="utf-8"))
    family_counts: dict[str, int] = {}
    assignments: dict[str, str] = {}
    for item in payload["productos"]:
        origin = item["origen"]
        product = type("SourceProduct", (), {
            "source_model_column": origin["columna_modelo"], "source_row": origin["fila"]
        })()
        family, status, _ = classification_for(product)
        assert family != NEEDS_CONFIRMATION
        assert status == "source_heading"
        assignments[item["id"]] = family
        family_counts[family] = family_counts.get(family, 0) + 1

    assert sum(family_counts.values()) == 283
    assert family_counts["Rastra de tiro con llantas tipo sur"] == 16
    assert family_counts["Rastra de tiro light"] == 10
    assert all(assignments[f"implementos-{row:04d}-I"] == "Rastra de tiro con llantas tipo sur" for row in range(5, 17))
    assert all(assignments[f"implementos-{row:04d}-E"] == "Rastra de tiro light" for row in range(71, 74))
