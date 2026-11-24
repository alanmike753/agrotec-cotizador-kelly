export type Rule = {
  id: number;
  scope_type: "family" | "product";
  scope_key: string;
  name: string;
  discounts: string[];
  explicit_zero: boolean;
  source: string;
  updated_at: string;
};

export type Calculation = {
  distributor_cost: string;
  suggested_price: string;
  profit_amount: string;
  effective_markup_pct: string;
  gross_margin_pct: string;
  profit_mode: "markup" | "fixed";
  profit_value: string;
  rounding_increment: "1" | "10" | "50" | "100";
  discounts_used?: string[];
  discount_origin?: "family" | "product" | "temporary";
};

export type CommercialPreference = {
  profit_mode: "markup" | "fixed";
  profit_value: string;
  rounding_increment: "1" | "10" | "50" | "100";
  is_custom: boolean;
  updated_at: string | null;
};

export type FamilySummary = {
  name: string;
  count: number;
  status: "source_heading" | "manual" | "needs_confirmation";
  source_label: string | null;
  has_rule: boolean;
};

export type Product = {
  id: string;
  name: string;
  supplier_code: string | null;
  category: "Implementos";
  family: string | null;
  family_status: "source_heading" | "manual" | "needs_confirmation";
  family_source_label: string | null;
  list_price_mxn: string;
  default_markup_pct: string | null;
  status: "configured" | "pending";
  commercial_preference: CommercialPreference;
  rule: Rule | null;
  calculation: Calculation | null;
  origin: { sheet: "Implementos"; row: number; model_column: string; price_column: string; updated_at: string };
};

export type ProductList = {
  items: Product[];
  filtered: number;
  counts: { total: number; configured: number; pending: number; family_confirmation: number };
  page: number;
  page_size: number;
};

export type AuthUser = {
  id: number;
  email: string;
  full_name: string;
  role: "admin" | "seller";
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
};

