import type { Product } from "./types.ts";
import { KELLY_BASE_DISCOUNTS } from "./discount-policy.ts";

export type QuoteCalculationPayload = {
  profit_mode: "markup" | "fixed";
  profit_value: string;
  rounding_increment: "1" | "10" | "50" | "100";
  discounts?: string[];
};

export function areDiscountsValid(values: string[]): boolean {
  if (values.length !== 3 || Number(values[0]) !== Number(KELLY_BASE_DISCOUNTS[0]) || Number(values[1]) !== Number(KELLY_BASE_DISCOUNTS[1])) return false;
  return values.every(value => {
    if (value.trim() === "") return false;
    const parsed = Number(value);
    return Number.isFinite(parsed) && parsed >= 0 && parsed <= 100;
  });
}

export function areDiscountsEqual(left: string[], right: string[]): boolean {
  return left.length === right.length && left.every((value, index) => Number(value) === Number(right[index]));
}

export function usesTemporaryDiscounts(product: Product, discounts: string[]): boolean {
  return areDiscountsValid(discounts) && (!product.rule || !areDiscountsEqual(discounts, product.rule.discounts));
}

export function buildCalculationPayload(
  product: Product,
  discounts: string[],
  profitMode: "markup" | "fixed",
  profitValue: string,
  roundingIncrement: "1" | "10" | "50" | "100",
): QuoteCalculationPayload {
  if (!areDiscountsValid(discounts)) throw new Error("Captura descuentos válidos para calcular.");
  const temporary = usesTemporaryDiscounts(product, discounts);
  return {
    profit_mode: profitMode,
    profit_value: profitValue,
    rounding_increment: roundingIncrement,
    ...(temporary ? { discounts: [...discounts] } : {}),
  };
}
