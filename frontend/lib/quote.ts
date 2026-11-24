import type { Calculation, Product } from "./types.ts";
import { mxn } from "./format.ts";

export function buildClientQuote(product: Product, calculation: Calculation): string {
  return [
    "Agrotec de Occidente",
    `Implemento Kelly: ${product.name}`,
    `Familia: ${product.family || "Por confirmar"}`,
    `Precio de venta: ${mxn(calculation.suggested_price)}`,
    "Moneda: MXN",
    "IVA: por confirmar",
  ].join("\n");
}
