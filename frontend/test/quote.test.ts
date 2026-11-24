import assert from "node:assert/strict";
import test from "node:test";
import { buildClientQuote } from "../lib/quote.ts";
import type { Calculation, Product } from "../lib/types.ts";

test("client quote contains sale data and excludes confidential commercial data", () => {
  const product = { name: "RASTRA 2424", family: "Rastras" } as Product;
  const calculation = { suggested_price: "42597" } as Calculation;
  const text = buildClientQuote(product, calculation);

  assert.match(text, /RASTRA 2424/);
  assert.match(text, /42,597/);
  assert.match(text, /MXN/);
  assert.doesNotMatch(text, /costo distribuidor|descuento|utilidad|ganancia|precio de lista/i);
});
