export type Severity = "critical" | "warning" | "info";
export type AnalysisStatus = "uploaded" | "processing" | "completed" | "failed";
export type ColumnKind = "integer" | "decimal" | "date" | "text" | "empty";
export type ExpectedType = "integer" | "decimal" | "text" | "date";
export type DecimalSeparator = "auto" | "comma" | "dot";
export type StatType = "quant_discrete" | "quant_continuous" | "nominal" | "ordinal" | "temporal" | "identifier";
export type WorkflowStatus = "analyzed" | "in_treatment" | "pending" | "ready_for_eda" | "eda_generated";

export interface User { id: string; name: string; email: string }

export interface ColumnInfo {
  name: string; dtype: ColumnKind; dtype_label: string; non_missing: number;
  stat_type?: StatType; stat_label?: string; stat_reasons?: string[];
}

export interface SuggestedConfig {
  types: Record<string, ExpectedType>;
  dates: string[];
  lat_column: string | null;
  lon_column: string | null;
}

export interface UploadProfile {
  id: string;
  status: AnalysisStatus;
  filename: string;
  size_bytes: number;
  sheets: string[];
  selected_sheet: string | null;
  n_rows: number;
  n_cols: number;
  encoding: string | null;
  delimiter: string | null;
  columns: ColumnInfo[];
  suggested_config: SuggestedConfig;
  preview: { columns: string[]; lines: number[]; rows: string[][] };
}

/** Configuração enviada ao backend (espelha app/schemas/validation.py). */
export interface AnalysisConfig {
  decimal_separator: DecimalSeparator;
  missing: { enabled: boolean; columns: string[] | null; markers: string[]; required_columns: string[] };
  duplicates: { enabled: boolean; key_columns: string[] | null };
  types: { enabled: boolean; expected: Record<string, ExpectedType>; date_format: string | null };
  ranges: { enabled: boolean; limits: Record<string, { min: number | null; max: number | null }>; suspect_columns: string[] };
  geo: { enabled: boolean; lat_column: string | null; lon_column: string | null };
  dates: {
    enabled: boolean; columns: string[]; date_format: string | null; flag_future: boolean;
    min_date: string | null; max_date: string | null;
  };
}
export interface RunPayload { sheet: string | null; config: AnalysisConfig; store_values: boolean; keep_data: boolean }

export interface AnalysisListItem {
  id: string; filename: string; file_type: string; status: AnalysisStatus;
  created_at: string; completed_at: string | null;
  total_rows: number; total_columns: number; total_issues: number; affected_rows: number;
  quality_score: number | null; rules_used: string[]; sheet: string | null;
  workflow_status: WorkflowStatus; current_version: number | null; data_available: boolean;
}
export interface Paginated<T> { total: number; page: number; page_size: number; items: T[] }

export interface InsightItem { level: "success" | "info" | "warning" | "critical"; title: string; text: string; recommendation: string }

export interface AnalysisResult extends AnalysisListItem {
  file_size_bytes: number;
  error_message: string | null;
  feedback_submitted?: boolean;
  store_values: boolean;
  metrics: {
    total_rows: number; total_columns: number; total_occurrences: number; affected_rows: number;
    affected_rows_pct: number; clean_rows: number; clean_rows_pct: number;
    by_category: { category: string; label: string; rule: string; count: number }[];
    by_severity: { severity: Severity; label: string; count: number }[];
    by_column: { column: string; count: number }[];
    missing_by_column: { column: string; count: number; pct: number }[];
  };
  score: { value: number | null; label: string; formula: string; disclaimer: string };
  rules: { code: string; letter: string; name: string; description: string; executed: boolean; issues: number; seconds: number }[];
  insights: { provider: string; llm_available: boolean; items: InsightItem[] };
  issues_truncated: boolean;
}

export interface IssueRow {
  id: number; row: number; column: string; value: string; category: string; category_label: string;
  severity: Severity; severity_label: string; description: string; suggestion: string;
}
export interface IssueQuery {
  q?: string; column?: string; category?: string; severity?: string;
  sort_by: string; descending: boolean; page: number; page_size: number;
}

export interface DashboardSummary {
  total_analyses: number; total_rows: number; total_issues: number;
  recent_analyses: number; recent_days: number; average_score: number | null;
}
export interface DashboardCharts {
  analyses_over_time: { date: string; count: number }[];
  issues_by_category: { category: string; label: string; count: number }[];
  recent_quality: { id: string; filename: string; score: number | null; completed_at: string }[];
}

export interface FeedbackPayload {
  usability_rating: number; usefulness_rating: number; would_use_again: "sim" | "talvez" | "nao";
  difficulties: string; suggestions: string;
}
export interface PublicSettings { max_upload_mb: number; allowed_extensions: string[]; default_markers: string[]; data_retention_days?: number; max_versions?: number }
export interface RulesCatalog { rules: { code: string; letter: string; name: string; description: string }[] }

// ------------------------------------------------------------------ tratamento de dados

export interface CleaningCounts {
  total: number; corrected: number; accepted: number; pending: number; introduced: number;
  affected_rows: number; progress_pct: number;
}
export interface ValidationSnapshot { rows: number; total_issues: number; affected_rows: number; pending: number; accepted: number; score: number | null }
export interface CleaningSummary {
  analysis_id: string; workflow_status: WorkflowStatus; current_version: number | null; data_available: boolean;
  message?: string; version_label?: string; counts: CleaningCounts;
  by_category: { category: string; label: string; initial: number; pending: number; accepted: number; corrected: number }[];
  before: Partial<ValidationSnapshot>; after: ValidationSnapshot;
  operations: { imputed_values: number; removed_rows: number; duplicates_resolved: number; manual_corrections: number; exceptions_accepted: number; operations: number };
  can_generate_eda: boolean; eda_generated_for_version: boolean; readiness_message: string; expires_at: string | null;
}
export interface ColumnStat {
  name: string; stat_type: StatType; label: string; source: "auto" | "manual"; reasons: string[];
  n_missing: number; n_unique: number; pct_missing: number; order?: string[] | null;
}
export interface MethodInfo { key: string; label: string; description: string; available: boolean; reason: string | null }
export interface Recommendation {
  method: string; label: string; justification: string; warnings: string[]; statistic?: string; group_by?: string[];
}
export interface ColumnProfile {
  column: string; stat_type: StatType; stat_label: string; n_total: number; n_missing: number; pct_missing: number; n_valid: number;
  n_unique: number; mean?: number; median?: number; mode?: number | string; skew?: number | null; outlier_count?: number;
  top_categories?: { value: string; count: number }[];
}
export interface ColumnOptions {
  version: number; stat_types: Record<StatType, string>; columns: ColumnStat[]; methodology: string[];
  profile?: ColumnProfile; recommendation?: Recommendation; methods?: MethodInfo[];
  group_candidates?: { column: string; eta_squared: number; n_groups: number; coverage: number }[];
  order_columns?: string[]; not_informed_text?: string;
}
export interface PendingIssue {
  row: number; column: string; value: string; category: string; category_label: string; severity: Severity;
  severity_label: string; description: string; suggestion: string; accepted: boolean;
}
export type CleaningAction =
  | "impute" | "remove_duplicates" | "merge_duplicates" | "set_value" | "mark_missing" | "convert_number"
  | "convert_date" | "clip" | "swap_latlon" | "remove_rows" | "accept_exception";
export interface CleaningRequest {
  base_version: number; action: CleaningAction; column?: string | null; scope?: "selected" | "column_all";
  rows?: number[]; cells?: Record<string, unknown>[]; params?: Record<string, unknown>;
  justification?: string | null; confirm?: boolean; acknowledge?: string[];
}
export interface PreviewResult {
  action: string; method: string; operation_type: string; column: string | null;
  n_changes: number; n_rows_affected: number; n_removed: number; n_exceptions: number;
  changes: { row: number; column: string; old: string; new: string; note: string }[]; changes_truncated: boolean;
  removed: { row: number; group: number | null; values: Record<string, string> }[]; removed_truncated: boolean;
  warnings: string[]; errors: string[]; notes: string[]; unresolved: number[];
  requires: { key: string; text: string }[]; requires_justification: boolean; parameters: Record<string, unknown>;
  impact?: { before: { pending: number; score: number | null; affected_rows: number }; after: { pending: number; score: number | null; affected_rows: number } };
}
export interface DuplicateRecord { row: number; values: Record<string, string>; filled: number }
export interface DuplicateGroup {
  id: number; rows: number[]; exact: boolean; conflicts: string[]; records: DuplicateRecord[];
  merge: { values: Record<string, string | null>; conflicts: string[] };
}
export interface DuplicatesInfo {
  version: number; key_columns: string[]; issue_column: string; total_groups: number; conflicting_groups: number;
  temporal_columns: string[]; groups: DuplicateGroup[]; truncated: boolean;
}
export interface OutlierResult {
  column: string; method: string; n_numeric: number; note: string; justification?: string; error?: string;
  lower?: number | null; upper?: number | null; n_candidates?: number;
  candidates: { row: number; value: string; number: number; reason: string }[];
}
export interface CleaningOperationRow {
  id: string; operation_type: string; operation_label: string; column: string | null; affected_rows: number; method: string | null;
  justification: string | null; from_version: number | null; to_version: number | null; undone: boolean; in_current_version: boolean;
  user: string; created_at: string; original_values: Record<string, unknown>[]; replacement_values: Record<string, unknown>[];
  values_truncated: boolean; parameters: Record<string, unknown> | null;
}
export interface VersionRow {
  id: string; version_number: number; label: string; parent_version_number: number | null; is_current: boolean;
  in_current_lineage: boolean; status: string; total_rows: number; total_columns: number; quality_score: number | null;
  created_at: string; data_available: boolean;
}

export interface DataPage {
  version: number; label: string; columns: string[]; total: number; total_rows: number; page: number; page_size: number;
  rows: { row: number; values: string[]; flags: Record<string, { severity: Severity; category: string; description: string }> }[];
}
