/** Typed client for the EchoMiner API. Same origin in production, so the
 *  session cookie travels without CORS gymnastics. */

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

export type JobFileSummary = {
  filename: string;
  pages: number | null;
  header_count: number | null;
  record_count: number;
  blank_row_count: number;
  status: string;
  warnings: string | null;
};

export type JobState = {
  id: string;
  status: string;
  file_count: number;
  record_count: number;
  engine_version: string | null;
  files: JobFileSummary[];
  purged: boolean;
};

export type PreviewPage = { columns: string[]; total: number; rows: Record<string, string>[] };

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}/api/v1${path}`, {
    credentials: "include",
    headers: init?.body instanceof FormData ? undefined : { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      /* response had no JSON body */
    }
    throw new ApiError(typeof detail === "string" ? detail : "Request failed", response.status);
  }
  return (await response.json()) as T;
}

export type RegistrationInput = {
  full_name: string;
  designation: string;
  affiliation: string;
  institute: string;
  taluk?: string;
  district?: string;
  state?: string;
  country_iso2: string;
  email: string;
  phone_e164?: string;
  project_title: string;
  project_description: string;
  purpose: string;
  agreement_accepted: boolean;
  agreement_text: string;
  captcha_token: string;
};

export const api = {
  register: (input: RegistrationInput) =>
    request<{ status: string }>("/registrations", { method: "POST", body: JSON.stringify(input) }),

  verifyOtp: (email: string, code: string) =>
    request<{ status: string; tool_unlocked: boolean }>("/auth/otp/verify", {
      method: "POST",
      body: JSON.stringify({ email, code }),
    }),

  resendOtp: (email: string, captcha_token: string) =>
    request<{ status: string }>("/auth/otp/resend", {
      method: "POST",
      body: JSON.stringify({ email, captcha_token }),
    }),

  restore: () => request<{ status: string }>("/auth/session/restore", { method: "POST" }),

  me: () => request<{ email: string; full_name: string }>("/me"),

  signOut: () => request<{ status: string }>("/auth/session", { method: "DELETE" }),

  submitJob: (files: File[]) => {
    const form = new FormData();
    files.forEach((file) => form.append("files", file));
    return request<{ id: string; status: string; file_count: number }>("/jobs", {
      method: "POST",
      body: form,
    });
  },

  job: (id: string) => request<JobState>(`/jobs/${id}`),

  preview: (id: string, limit = 50, offset = 0) =>
    request<PreviewPage>(`/jobs/${id}/preview?limit=${limit}&offset=${offset}`),

  exportUrl: (id: string) => `${BASE}/api/v1/jobs/${id}/export.xlsx`,

  discard: (id: string) => request<{ status: string }>(`/jobs/${id}`, { method: "DELETE" }),
};
