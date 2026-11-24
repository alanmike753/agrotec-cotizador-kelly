from decimal import Decimal

import pytest

from app.calculations import apply_successive_discounts, calculate_sale, commercial_round


def test_mandatory_rastra_without_cleaners():
    result = calculate_sale(Decimal("82278"), [Decimal("57.5"), Decimal("3"), Decimal("10")], "markup", Decimal("25"), "1")
    assert result["distributor_cost"] == Decimal("30527.19")
    assert result["suggested_price"] == Decimal("38159")


def test_mandatory_rastra_with_cleaners():
    result = calculate_sale(Decimal("90780"), [Decimal("57.5"), Decimal("3"), Decimal("10")], "markup", Decimal("25"), "1")
    assert result["distributor_cost"] == Decimal("33681.65")
    assert result["suggested_price"] == Decimal("42102")


def test_discounts_are_successive_not_additive():
    assert apply_successive_discounts(Decimal("100"), [Decimal("10"), Decimal("10")]) == Decimal("81.00")


@pytest.mark.parametrize(("increment", "expected"), [("1", "123"), ("10", "130"), ("50", "150"), ("100", "200")])
def test_rounding_modes(increment, expected):
    assert commercial_round(Decimal("123.40"), increment) == Decimal(expected)


def test_fixed_profit_and_real_margin():
    result = calculate_sale(Decimal("100"), [Decimal("0")], "fixed", Decimal("25"), "1")
    assert result["profit_amount"] == Decimal("25.00")
    assert result["gross_margin_pct"] == Decimal("20.00")

