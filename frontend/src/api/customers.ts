/**
 * Endpoint functions for /api/v1/customers/. Types mirror the backend's
 * CustomerSerializer (output) and Customer{Create,Update}Serializer (input).
 */
import { apiRequest, type Paginated } from "@/api/client";

export type CustomerType = "PERSON" | "COMPANY";
export type CustomerStatus = "ACTIVE" | "INACTIVE";

export interface Customer {
  id: string;
  external_customer_id: string;
  customer_type: CustomerType;
  name: string;
  email: string;
  phone: string;
  address_line1: string;
  address_line2: string;
  postal_code: string;
  city: string;
  country_code: string;
  status: CustomerStatus;
  created_at: string;
  updated_at: string;
}

/** POST body. `status` is not here: it only changes through deactivate/reactivate. */
export type CustomerCreateInput = Omit<Customer, "id" | "status" | "created_at" | "updated_at">;

/** PATCH body: any subset of fields. The external id is fixed after creation. */
export type CustomerUpdateInput = Partial<Omit<CustomerCreateInput, "external_customer_id">>;

/** Sort options the backend allows (selectors.ALLOWED_ORDERINGS). */
export type CustomerOrdering =
  | "name"
  | "-name"
  | "external_customer_id"
  | "-external_customer_id"
  | "created_at"
  | "-created_at";

export interface CustomerListParams {
  page?: number;
  page_size?: number;
  search?: string;
  status?: CustomerStatus;
  customer_type?: CustomerType;
  ordering?: CustomerOrdering;
}

export function listCustomers(params: CustomerListParams, signal?: AbortSignal) {
  return apiRequest<Paginated<Customer>>("/customers/", { query: { ...params }, signal });
}

export function getCustomer(id: string, signal?: AbortSignal) {
  return apiRequest<Customer>(`/customers/${id}/`, { signal });
}

export function createCustomer(input: CustomerCreateInput) {
  return apiRequest<Customer>("/customers/", { method: "POST", body: input });
}

export function updateCustomer(id: string, input: CustomerUpdateInput) {
  return apiRequest<Customer>(`/customers/${id}/`, { method: "PATCH", body: input });
}

export function deactivateCustomer(id: string) {
  return apiRequest<Customer>(`/customers/${id}/deactivate/`, { method: "POST" });
}

export function reactivateCustomer(id: string) {
  return apiRequest<Customer>(`/customers/${id}/reactivate/`, { method: "POST" });
}
