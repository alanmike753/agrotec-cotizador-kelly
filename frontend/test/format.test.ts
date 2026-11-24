import assert from "node:assert/strict";
import test from "node:test";
import { mxn } from "../lib/format.ts";

test("mxn formats amounts with Mexican thousands separators", () => {
  assert.match(mxn("38608"), /38,608/);
});

