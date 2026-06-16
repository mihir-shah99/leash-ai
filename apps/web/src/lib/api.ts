// Centralized API access for the dashboard.
//
// The base URL and (dev) API key come from Vite env vars so the app is
// deployable instead of hardcoding http://localhost:8000. The control plane
// now requires a Bearer API key, so we attach one when VITE_API_KEY is set.

export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

const API_KEY: string | undefined = import.meta.env.VITE_API_KEY;

export function apiUrl(path: string): string {
  const base = API_BASE_URL.replace(/\/$/, "");
  return `${base}${path.startsWith("/") ? path : `/${path}`}`;
}

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  if (API_KEY) headers.set("Authorization", `Bearer ${API_KEY}`);
  return fetch(apiUrl(path), { ...init, headers });
}
