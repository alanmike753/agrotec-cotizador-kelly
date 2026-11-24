from __future__ import annotations

from decimal import Decimal


FIXED_FIRST_DISCOUNT = Decimal("57.5")
FIXED_SECOND_DISCOUNT = Decimal("3")
DEFAULT_THIRD_DISCOUNT = Decimal("10")
BASE_DISCOUNTS = ["57.5", "3", "10"]


def validate_kelly_discounts(values: list[str], *, label: str = "Los descuentos") -> list[str]:
    from decimal import InvalidOperation

    if len(values) != 3:
        raise ValueError(f"{label} deben contener exactamente tres etapas.")
    parsed: list[Decimal] = []
    for value in values:
        try:
            number = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError(f"{label} deben ser decimales válidos.") from exc
        if number < 0 or number > 100:
            raise ValueError("Cada descuento debe estar entre 0 y 100.")
        parsed.append(number)
    if parsed[0] != FIXED_FIRST_DISCOUNT or parsed[1] != FIXED_SECOND_DISCOUNT:
        raise ValueError("La política Kelly exige 57.5% y 3% como los dos primeros descuentos fijos.")
    return [format(number, "f") for number in parsed]
