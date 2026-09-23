/** Admin API client. Separate cookie realm from the researcher session. */

export type UserRow = {
  id: string; email: string; full_name: string; designation: string; affiliation: string;
  institute: string; taluk: string | null; district: string | null; state: string | null;
  country_iso2: string; phone_e164: string | null; project_title: string;
  project_description: string; purpose: string; status: string;
  email_verified_at: string | null; created_at: string | null;
};

export type UsagePayload = {
  summary: {
    users_total: number; users_active: number; jobs_total: number;
    files_total: number; records_total: number; downloads_total: number;
  };
  timeseries: { day: string; registrations: number; jobs: number; downloads: number }[];
};

export type GeoPayload = {
  states: { state: string; count: number }[];
  countries: { country: string; count: number }[];
};

export type OtpEntry = {
  email: string; purpose: string; attempts: number; verified: boolean;
  locked: boolean; expires_at: string; created_at: string | null;
};

export type ContentRow = {
  id: string; kind: string; slug: string; title: string; body_md: string;
  link_url: string | null; published_at: string | null; sort_order: number;
};

export type HealthPayload = {
  queue_depth: number; running: number; purge_backlog: number;
  failed_jobs: number; status: string;
};

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1/admin${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) throw new Error(String(response.status));
  return (await response.json()) as T;
}

export const adminApi = {
  login: (email: string, password: string, totp_code: string) =>
    call<{ status: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password, totp_code: totp_code || null }),
    }),
  me: () => call<{ email: string; role: string }>("/me"),
  signOut: () => call<{ status: string }>("/auth/session", { method: "DELETE" }),
  users: (params: Record<string, string>) =>
    call<{ total: number; items: UserRow[] }>(`/users?${new URLSearchParams(params)}`),
  setStatus: (id: string, status: string) =>
    call<{ status: string }>(`/users/${id}/status`, {
      method: "POST",
      body: JSON.stringify({ status }),
    }),
  usage: () => call<UsagePayload>("/analytics/usage"),
  geo: () => call<GeoPayload>("/analytics/geo"),
  projects: () => call<{ project: string; count: number }[]>("/analytics/projects"),
  otpLogs: () => call<OtpEntry[]>("/otp-logs"),
  health: () => call<HealthPayload>("/health"),
  content: (kind: string) => call<ContentRow[]>(`/content/${kind}`),
  saveContent: (body: Record<string, unknown>) =>
    call<ContentRow>("/content", { method: "POST", body: JSON.stringify(body) }),
  deleteContent: (id: string) =>
    call<{ status: string }>(`/content/${id}`, { method: "DELETE" }),
};
