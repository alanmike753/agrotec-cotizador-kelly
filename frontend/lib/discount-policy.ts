export const KELLY_BASE_DISCOUNTS = ["57.5", "3", "10"] as const;

export function freshKellyDiscounts(): string[] {
  return [...KELLY_BASE_DISCOUNTS];
}
