import assert from "node:assert/strict";
import test from "node:test";
import { areDiscountsValid, buildCalculationPayload, usesTemporaryDiscounts } from "../lib/quote-calculation.ts";
import type { Product } from "../lib/types.ts";

const pending = { id: "implementos-0051-E", rule: null } as Product;

test("pending products send valid decimal discounts as a temporary calculation", () => {
  const discounts = ["57.5", "3", "10"];
  assert.equal(areDiscountsValid(discounts), true);
  assert.equal(usesTemporaryDiscounts(pending, discounts), true);
  assert.deepEqual(buildCalculationPayload(pending, discounts, "markup", "25", "1"), {
    profit_mode: "markup",
    profit_value: "25",
    rounding_increment: "1",
    discounts,
  });
});

test("an explicit temporary zero discount is valid", () => {
  assert.equal(areDiscountsValid(["57.5", "3", "0"]), true);
  assert.deepEqual(buildCalculationPayload(pending, ["57.5", "3", "0"], "markup", "25", "1").discounts, ["57.5", "3", "0"]);
});

test("incomplete or out-of-range discounts remain blocked", () => {
  assert.equal(areDiscountsValid(["57.5", "3", ""]), false);
  assert.equal(areDiscountsValid(["57", "3", "10"]), false);
  assert.equal(areDiscountsValid(["57.5", "3", "101"]), false);
});
