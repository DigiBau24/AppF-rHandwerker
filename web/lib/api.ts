import { supabase } from "./supabase";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Ampel = "green" | "yellow" | "red";
// Beträge kommen als Strings (Decimal) vom Backend
export interface ProjectStatus {
  projekt_id: string;
  projekt_name: string;
  budget_netto: string;
  material_kosten: string;
  lohnkosten: string;
  gesamtkosten: string;
  restbudget: string;
  budget_verbrauch_prozent: string | null;
  status_ampel: Ampel;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      ...(init.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = body?.detail;
    throw new ApiError(
      res.status,
      typeof detail === "string" ? detail : "Eingabe ungültig oder Anfrage fehlgeschlagen."
    );
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const eur = (v: string | number) =>
  new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" }).format(Number(v));
