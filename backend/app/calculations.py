from __future__ import annotations

from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP


CENT = Decimal("0.01")
ONE = Decimal("1")
HUNDRED = Decimal("100")
ALLOWED_ROUNDING = {"1": Decimal("1"), "10": Decimal("10"), "50": Decimal("50"), "100": Decimal("100")}


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def apply_successive_discounts(list_price: Decimal, discounts: list[Decimal]) -> Decimal:
    amount = list_price
    for discount in discounts:
        if discount < 0 or discount > 100:
            raise ValueError("Cada descuento debe estar entre 0 y 100.")
        amount *= ONE - (discount / HUNDRED)
    return money(amount)


def commercial_round(value: Decimal, increment: str) -> Decimal:
    unit = ALLOWED_ROUNDING.get(increment)
    if unit is None:
        raise ValueError("Redondeo no válido.")
    if unit == ONE:
        return value.quantize(ONE, rounding=ROUND_HALF_UP)
    return (value / unit).to_integral_value(rounding=ROUND_CEILING) * unit


def calculate_sale(
    list_price: Decimal,
    discounts: list[Decimal],
    profit_mode: str,
    profit_value: Decimal,
    rounding_increment: str,
) -> dict[str, Decimal]:
    if profit_value < 0:
        raise ValueError("La ganancia no puede ser negativa.")
    cost = apply_successive_discounts(list_price, discounts)
    if profit_mode == "markup":
        raw_sale = cost * (ONE + profit_value / HUNDRED)
    elif profit_mode == "fixed":
        raw_sale = cost + profit_value
    else:
        raise ValueError("Tipo de ganancia no válido.")
    suggested = commercial_round(raw_sale, rounding_increment)
    profit = money(suggested - cost)
    markup = money((profit / cost) * HUNDRED) if cost else Decimal("0.00")
    gross_margin = money((profit / suggested) * HUNDRED) if suggested else Decimal("0.00")
    return {
        "distributor_cost": cost,
        "suggested_price": suggested,
        "profit_amount": profit,
        "effective_markup_pct": markup,
        "gross_margin_pct": gross_margin,
    }


def decimal_string(value: Decimal) -> str:
    return format(value, "f")

