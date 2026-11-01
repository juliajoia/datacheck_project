import { api } from "@/lib/api";
import type { EdaConfigPayload, EdaDetail, EdaListItem, EdaOptions } from "@/types/eda";
import type {
  AnalysisListItem, AnalysisResult, DataPage, CleaningOperationRow, CleaningRequest, CleaningSummary, ColumnOptions, DuplicatesInfo,
  OutlierResult, PendingIssue, PreviewResult, VersionRow, DashboardCharts, DashboardSummary, FeedbackPayload, IssueQuery, IssueRow,
  Paginated, PublicSettings, RulesCatalog, RunPayload, UploadProfile, User,
} from "@/types";

async function saveBlob(path: string, params: Record<string, unknown>, name: string) {
  const res = await api.get<Blob>(path, { params, responseType: "blob" });
  const url = URL.createObjectURL(res.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

export const authService = {
  register: (b: { name: string; email: string; password: string }) => api.post<User>("/auth/register", b).then((r) => r.data),
  login: (b: { email: string; password: string }) => api.post<User>("/auth/login", b).then((r) => r.data),
  logout: () => api.post("/auth/logout").then(() => undefined),
  me: () => api.get<User>("/auth/me").then((r) => r.data),
};

export const analysisService = {
  upload(file: File, onProgress?: (pct: number) => void) {
    const form = new FormData();
    form.append("file", file);
    return api
      .post<UploadProfile>("/analyses/upload", form, {
        onUploadProgress: (e) => e.total && onProgress?.(Math.round((e.loaded / e.total) * 100)),
      })
      .then((r) => r.data);
  },
  uploadSample: (n: "1" | "2") => api.post<UploadProfile>(`/analyses/upload-sample/${n}`).then((r) => r.data),
  profile: (id: string, sheet: string) => api.get<UploadProfile>(`/analyses/${id}/profile`, { params: { sheet } }).then((r) => r.data),
  run: (id: string, payload: RunPayload) => api.post<AnalysisResult>(`/analyses/${id}/run`, payload).then((r) => r.data),
  list: (page = 1, pageSize = 20) =>
    api.get<Paginated<AnalysisListItem>>("/analyses", { params: { page, page_size: pageSize } }).then((r) => r.data),
  get: (id: string) => api.get<AnalysisResult>(`/analyses/${id}`).then((r) => r.data),
  remove: (id: string) => api.delete(`/analyses/${id}`).then(() => undefined),
  data: (id: string, params: { q?: string; page: number; page_size: number; version?: number }) =>
    api.get<DataPage>(`/analyses/${id}/data`, { params }).then((r) => r.data),
  issues: (id: string, q: IssueQuery) =>
    api.get<Paginated<IssueRow>>(`/analyses/${id}/issues`, { params: q }).then((r) => r.data),
  feedback: (id: string, b: FeedbackPayload) => api.post(`/analyses/${id}/feedback`, b).then(() => undefined),
  async download(id: string, format: "csv" | "xlsx", filename: string) {
    await saveBlob(`/analyses/${id}/export`, { format }, `datacheck_${filename.replace(/\.[^.]+$/, "")}.${format}`);
  },
  /** Tabela de inconsistências (mesmas colunas da visão detalhada). */
  async downloadIssues(id: string, format: "xlsx" | "pdf", filename: string) {
    await saveBlob(`/analyses/${id}/export/issues`, { format }, `datacheck_inconsistencias_${filename.replace(/\.[^.]+$/, "")}.${format}`);
  },
};

export const dashboardService = {
  summary: () => api.get<DashboardSummary>("/dashboard/summary").then((r) => r.data),
  charts: () => api.get<DashboardCharts>("/dashboard/charts").then((r) => r.data),
};

export const metaService = {
  settings: () => api.get<PublicSettings>("/settings").then((r) => r.data),
  rules: () => api.get<RulesCatalog>("/rules").then((r) => r.data),
};

export const cleaningService = {
  summary: (id: string) => api.get<CleaningSummary>(`/analyses/${id}/cleaning/summary`).then((r) => r.data),
  options: (id: string, column?: string) =>
    api.get<ColumnOptions>(`/analyses/${id}/cleaning/options`, { params: column ? { column } : undefined }).then((r) => r.data),
  setColumnTypes: (id: string, types: Record<string, { type: string | null; order?: string[] }>) =>
    api.put<ColumnOptions>(`/analyses/${id}/cleaning/column-types`, { types }).then((r) => r.data),
  issues: (id: string, params: Record<string, unknown>) =>
    api.get<Paginated<PendingIssue> & { version: number }>(`/analyses/${id}/cleaning/issues`, { params }).then((r) => r.data),
  duplicates: (id: string) => api.get<DuplicatesInfo>(`/analyses/${id}/cleaning/duplicates`).then((r) => r.data),
  outliers: (id: string, body: { column: string; method: string; params: Record<string, unknown> }) =>
    api.post<OutlierResult>(`/analyses/${id}/cleaning/outliers`, body).then((r) => r.data),
  coordinateSuggestions: (id: string) =>
    api.get<{ lat_column: string | null; lon_column: string | null; suggestions: { row: number; latitude: string; longitude: string; reason: string }[] }>(
      `/analyses/${id}/cleaning/coordinate-suggestions`).then((r) => r.data),
  preview: (id: string, body: CleaningRequest) => api.post<PreviewResult>(`/analyses/${id}/cleaning/preview`, body).then((r) => r.data),
  apply: (id: string, body: CleaningRequest) =>
    api.post<{ version: number; label: string; summary: CleaningSummary }>(`/analyses/${id}/cleaning/apply`, { ...body, confirm: true }).then((r) => r.data),
  undo: (id: string) => api.post<CleaningSummary>(`/analyses/${id}/cleaning/undo`).then((r) => r.data),
  validate: (id: string) => api.post<CleaningSummary>(`/analyses/${id}/cleaning/validate`).then((r) => r.data),
  history: (id: string) => api.get<CleaningOperationRow[]>(`/analyses/${id}/cleaning/history`).then((r) => r.data),
  versions: (id: string) => api.get<VersionRow[]>(`/analyses/${id}/versions`).then((r) => r.data),
  restore: (id: string, versionNumber: number) =>
    api.post<CleaningSummary>(`/analyses/${id}/versions/${versionNumber}/restore`).then((r) => r.data),
  async download(id: string, params: Record<string, unknown>, filename: string) {
    await saveBlob(`/analyses/${id}/cleaning/export`, params, `datacheck_tratada_${filename.replace(/\.[^.]+$/, "")}.${params.format as string}`);
  },
};

export const edaService = {
  options: (id: string, version?: number) =>
    api.get<EdaOptions>(`/analyses/${id}/eda/options`, { params: version != null ? { version_number: version } : undefined }).then((r) => r.data),
  generate: (id: string, cfg: EdaConfigPayload) => api.post<EdaDetail>(`/analyses/${id}/eda/generate`, cfg).then((r) => r.data),
  list: () => api.get<EdaListItem[]>("/eda").then((r) => r.data),
  get: (id: string) => api.get<EdaDetail>(`/eda/${id}`).then((r) => r.data),
  regenerate: (id: string) => api.post<EdaDetail>(`/eda/${id}/regenerate`).then((r) => r.data),
  remove: (id: string) => api.delete(`/eda/${id}`).then(() => undefined),
  async download(id: string, format: "pdf" | "xlsx", name: string) {
    await saveBlob(`/eda/${id}/download`, { format }, `datacheck_eda_${name.replace(/[^\w-]+/g, "_")}.${format}`);
  },
};
