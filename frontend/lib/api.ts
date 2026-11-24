import { Calculation, Product, ProductList } from "./types";

export const API_URL = "";

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    credentials: "same-origin",
    cache: "no-store",
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: "No se pudo completar la solicitud." }));
    throw new ApiError(typeof detail.detail === "string" ? detail.detail : "Datos no válidos.", response.status);
  }
  return response.json();
}

export function getProducts(params = ""): Promise<ProductList> { return request(`/api/products?${params}`); }
export function getProduct(id: string): Promise<Product> { return request(`/api/products/${encodeURIComponent(id)}`); }
export function calculateProduct(id: string, body: object) {
  return request<Calculation>(`/api/products/${encodeURIComponent(id)}/calculate`, { method: "POST", body: JSON.stringify(body) });
}
export { request };

