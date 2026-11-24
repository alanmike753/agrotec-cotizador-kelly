from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Product


NEEDS_CONFIRMATION = "Familia por confirmar"


@dataclass(frozen=True)
class FamilyRange:
    column: str
    start_row: int
    end_row: int
    family: str
    source_label: str


# Ranges come only from section headings in the Implementos worksheet. Products
# without an unambiguous heading remain in the explicit review bucket.
FAMILY_RANGES = [
    FamilyRange("A", 9, 21, "Cultivadoras ajustables y timones", "CULTIVADORAS AJUSTABLES / TIMONES"),
    FamilyRange("A", 24, 30, "Marcos y cuadros", "MARCOS Y CUADROS"),
    FamilyRange("A", 33, 41, "Barras", "BARRAS"),
    FamilyRange("A", 44, 54, "Borderos", "BORDEROS"),
    FamilyRange("A", 73, 83, "Rastra de tiro pesada con llantas", "RASTRA T PESADA C/LLANTAS"),
    FamilyRange("A", 87, 105, "Rastra de levante tipo II sin limpiadores", "RASTRA LEVANTE TIPO II SIN LIMPIADORES"),
    FamilyRange("A", 109, 115, "Rastra de tiro light", "RASTRA DE TIRO LIGHT"),
    FamilyRange("A", 134, 134, "Rastra de levante cañera", "RASTRA LEVANTE CAÑERA"),
    FamilyRange("A", 139, 146, "Rastra de levante Hort y Pony sin limpiadores", "RASTRA DE LEV. TIPO HORT Y PONY SIN LIMPIADORES"),
    FamilyRange("A", 150, 157, "Rastra de levante Hort y Pony con limpiadores", "RASTRA DE LEV. TIPO HORT Y PONY CON LIMPIADORES"),
    FamilyRange("A", 161, 164, "Arado zanjeador", "ARADO ZANJEADOR"),
    FamilyRange("A", 165, 167, "Plumas de levante", "PLUMAS DE LEVANTE"),
    FamilyRange("E", 7, 23, "Subsuelos", "SUBSUELOS"),
    FamilyRange("E", 26, 47, "Cultivadoras", "CULTIVADORAS"),
    FamilyRange("E", 50, 53, "Rastra de tiro con llantas tipo sur", "RASTRA TIRO C/LLANTAS TIPO SUR"),
    FamilyRange("E", 71, 73, "Rastra de tiro light", "RASTRA DE TIRO LIGHT (continuación entre bloques)"),
    FamilyRange("E", 77, 95, "Rastra de levante tipo II con limpiadores", "RASTRA LEVANTE TIPO II CON LIMPIADORES"),
    FamilyRange("E", 99, 103, "Rastra de levante tipo IV con manivela sin limpiadores", "RASTRA DE LEV. TIPO IV CON MANIVELA SIN LIMPIADORES"),
    FamilyRange("E", 107, 111, "Rastra de levante tipo IV con manivela con limpiadores", "RASTRA DE LEV. TIPO IV CON MANIVELA CON LIMPIADORES"),
    FamilyRange("E", 135, 137, "Arados hidráulicos", "ARADOS HIDRÁULICOS"),
    FamilyRange("E", 141, 151, "Ensiladores de forraje con llantas", "ENSILADORES DE FORRAJE CON LLANTAS"),
    FamilyRange("E", 154, 163, "Cama baja con llantas sin rampas", "ENS. CAMA BAJA C/LLANTAS SIN RAMPAS"),
    FamilyRange("E", 166, 171, "Cama baja con llantas con rampas", "ENS. CAMA BAJA C/LLANTAS CON RAMPAS"),
    FamilyRange("I", 5, 16, "Rastra de tiro con llantas tipo sur", "RASTRA TIRO C/LLANTAS TIPO SUR (continuación entre bloques)"),
    FamilyRange("I", 21, 31, "Rastra de tiro tipo sur reforzada", "RASTRA TIRO C/LLANTAS TIPO SUR REFORZADAS"),
    FamilyRange("I", 36, 42, "Rastra de tiro reforzada doble rodado", "RASTRA TIRO REFORZADAS / DOBLE RODADO"),
    FamilyRange("I", 46, 56, "Rastra de tiro ligera con llantas", "RASTRA T LIGERA C/LLANTAS"),
    FamilyRange("I", 73, 77, "Rastra de levante tipo IV con torre fija sin limpiadores", "RASTRA DE LEV. TIPO IV CON TORRE FIJA SIN LIMPIADORES"),
    FamilyRange("I", 81, 85, "Rastra de levante tipo IV con torre fija con limpiadores", "RASTRA DE LEV. TIPO IV CON TORRE FIJA CON LIMPIADORES"),
    FamilyRange("I", 89, 99, "Rastra de levante tipo V sin limpiadores", "RASTRA DE LEV. TIPO V SIN LIMPIADORES"),
    FamilyRange("I", 103, 113, "Rastra de levante tipo V con limpiadores", "RASTRA DE LEV. TIPO V CON LIMPIADORES"),
    FamilyRange("I", 135, 140, "Cama baja reforzada 6 t hidráulica 2 puntos", "ENS. CAMA BAJA C/LLANTAS REF 6 TON HID 2 P"),
]


def classification_for(product: Product) -> tuple[str, str, str]:
    for item in FAMILY_RANGES:
        if item.column == product.source_model_column and item.start_row <= product.source_row <= item.end_row:
            return item.family, "source_heading", item.source_label
    return NEEDS_CONFIRMATION, "needs_confirmation", "Sin encabezado inequívoco en la hoja Implementos"


def classify_catalog(db: Session, overwrite: bool = False) -> dict[str, int]:
    products = db.scalars(select(Product)).all()
    counts = {"classified": 0, "needs_confirmation": 0, "preserved": 0}
    for product in products:
        family, status, label = classification_for(product)
        if not overwrite and product.family_status == "manual":
            product.family_source_label = product.family_source_label or "Asignación local preservada"
            counts["preserved"] += 1
            continue
        product.family = family
        product.family_status = status
        product.family_source_label = label
        counts["needs_confirmation" if status == "needs_confirmation" else "classified"] += 1
    db.commit()
    return counts

