import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "https://vmuzexvtbodnkzhfitzf.supabase.co";
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

export interface ProblemDetails {
  type?: string;
  title?: string;
  status?: number;
  detail: string;
  instance?: string;
}

export class ProblemDetailsError extends Error {
  status: number;
  title: string;
  detail: string;
  instance?: string;

  constructor(status: number, detail: string, title?: string, instance?: string) {
    super(detail);
    this.name = "ProblemDetailsError";
    this.status = status;
    this.detail = detail;
    this.title = title || "API Request Error";
    this.instance = instance;
  }
}

let activeDemoToken: string | null = null;

export function setActiveDemoToken(token: string | null) {
  activeDemoToken = token;
}

export async function getAuthToken(): Promise<string | null> {
  if (activeDemoToken) return activeDemoToken;
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token || null;
}

export async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const cleanEndpoint = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
  const url = `${API_BASE_URL}/api/v1${cleanEndpoint}`;

  // Retrieve token: from active demo token or Supabase session
  let token = activeDemoToken;
  if (!token) {
    const { data } = await supabase.auth.getSession();
    token = data.session?.access_token || null;
  }

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  // Zero-PHI Console Policy: Log route and method only, never log payloads or PII
  if (process.env.NODE_ENV !== "production") {
    console.info(`[API Request] ${options.method || "GET"} ${cleanEndpoint}`);
  }

  const res = await fetch(url, {
    ...options,
    headers,
  });

  if (!res.ok) {
    let errorDetail = `Request failed with status ${res.status}`;
    let errorTitle = "Request Failed";
    let instance: string | undefined;

    try {
      const errJson = await res.json();
      if (errJson.detail) {
        errorDetail = typeof errJson.detail === "string" ? errJson.detail : JSON.stringify(errJson.detail);
      }
      if (errJson.title) errorTitle = errJson.title;
      if (errJson.instance) instance = errJson.instance;
    } catch {
      // If not JSON, use default status text
      errorDetail = res.statusText || errorDetail;
    }

    throw new ProblemDetailsError(res.status, errorDetail, errorTitle, instance);
  }

  if (res.status === 204) {
    return {} as T;
  }

  return res.json() as Promise<T>;
}
