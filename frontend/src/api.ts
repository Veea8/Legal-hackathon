import type {
  ApplyResponse,
  CheckResult,
  DeliveryPreview,
  DeliveryRecord,
  DeliveryRequest,
  DemoFormInfo,
  FormSchema,
  HealthResponse,
  KBEntry,
  RuleOverride,
  RuleSet,
  SendResponse,
} from "./types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export function errorMessage(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

function detailOf(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const d = (body as { detail: unknown }).detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) {
      return d
        .map((e) => (e && typeof e === "object" && "msg" in e ? String((e as { msg: unknown }).msg) : JSON.stringify(e)))
        .join("; ");
    }
  }
  return fallback;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api${path}`, init);
  const text = await res.text();
  let body: unknown = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = text;
  }
  if (!res.ok) throw new ApiError(res.status, detailOf(body, `${res.status} ${res.statusText}`));
  return body as T;
}

const json = (method: string, data: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(data),
});

export const api = {
  health: () => request<HealthResponse>("/health"),
  kb: () => request<KBEntry[]>("/kb"),
  demoForms: () => request<DemoFormInfo[]>("/demo-forms"),
  createDemo: (form_id: string) => request<FormSchema>("/forms", json("POST", { source: "demo", form_id })),
  createFromSchema: (schema: FormSchema, demo_form_id?: string) =>
    request<FormSchema>("/forms", json("POST", { source: "schema", schema, demo_form_id })),
  createPaste: (text: string, name?: string, business_context?: string) =>
    request<FormSchema>("/forms", json("POST", { source: "paste", text, name, business_context })),
  upload: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<FormSchema[]>("/forms/upload", { method: "POST", body: fd });
  },
  getForm: (id: string) => request<FormSchema>(`/forms/${id}`),
  updateForm: (id: string, schema: FormSchema) => request<FormSchema>(`/forms/${id}`, json("PUT", schema)),
  checks: (id: string) => request<CheckResult[]>(`/forms/${id}/checks`),
  analyze: (id: string, live = false) => request<RuleSet>(`/forms/${id}/analyze?live=${live}`, { method: "POST" }),
  analysis: (id: string) => request<RuleSet>(`/forms/${id}/analysis`),
  putRules: (id: string, overrides: RuleOverride[]) => request<RuleSet>(`/forms/${id}/rules`, json("PUT", { overrides })),
  apply: (id: string) => request<ApplyResponse>(`/forms/${id}/apply`, { method: "POST" }),
  reportUrl: (id: string, format: "json" | "csv" | "html" | "ics") => `/api/forms/${id}/report?format=${format}`,

  // integrations
  deliveries: (id: string) => request<DeliveryRecord[]>(`/forms/${id}/deliveries`),
  previewDelivery: (id: string, req: DeliveryRequest) =>
    request<DeliveryPreview>(`/forms/${id}/deliveries/preview`, json("POST", req)),
  sendDelivery: (id: string, req: DeliveryRequest) =>
    request<SendResponse>(`/forms/${id}/deliveries`, json("POST", req)),
};
