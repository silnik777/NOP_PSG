/** Typed-ish API client. All endpoints share the same origin (/api/v1). */

export class ApiError extends Error {
  status: number;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
  }
}

async function request<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? undefined : { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await res.text();
  let data: any = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!res.ok) {
    const detail =
      typeof data === "object" && data?.detail
        ? typeof data.detail === "string"
          ? data.detail
          : JSON.stringify(data.detail, null, 2)
        : `HTTP ${res.status}`;
    throw new ApiError(res.status, detail);
  }
  return data as T;
}

export const get = <T = any>(path: string) => request<T>(path);
export const post = <T = any>(path: string, body: unknown) => request<T>(path, body);

export interface Qty {
  value: number;
  unit: string;
}

/** Reference gas profiles for composition pickers. */
export interface RefProfile {
  code: string;
  name: string;
  fractions: Record<string, number>;
}
export const loadProfiles = () => get<RefProfile[]>("/api/v1/reference-profiles");

export const fmt = (v: number | null | undefined, digits = 2): string =>
  v === null || v === undefined ? "—" : v.toLocaleString("pl-PL", { maximumFractionDigits: digits });
