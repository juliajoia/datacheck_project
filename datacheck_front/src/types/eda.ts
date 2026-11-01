export type EdaStatus = "queued" | "processing" | "completed" | "failed";

export interface EdaConfigPayload {
  report_name: string;
  version_number?: number | null;
  sections: string[];
  columns: string[];
  correlation_method: "pearson" | "spearman";
  percentiles: number[];
  temporal: { date_column: string | null; frequency: "D" | "M" | "Y"; value_columns: string[] };
}

export interface EdaOptions {
  version: { number: number; label: string; created_at: string | null; rows: number; columns: number; quality_score: number | null };
  readiness: { pending: number; accepted: number; score: number | null; ready: boolean };
  message: string | null;
  sections: { key: string; label: string; ok: boolean; reason?: string | null }[];
  columns: { name: string; stat_type: string; label: string; n_valid: number }[];
  temporal_columns: string[];
  numeric_columns: string[];
}

export interface EdaListItem {
  id: string; analysis_id: string; analysis_name: string; report_name: string; version_number: number; version_label: string;
  total_rows: number; total_columns: number; sections: string[]; sections_labels: string[]; status: EdaStatus;
  error_message: string | null; created_at: string | null; completed_at: string | null; has_files: boolean;
  configuration: EdaConfigPayload;
}

export interface DescriptiveRow {
  column: string; n_valid: number; n_missing: number; mean?: number | null; median?: number | null; mode?: number | null; min?: number | null; max?: number | null;
  range?: number | null; variance?: number | null; std?: number | null; cv?: number | null; q1?: number | null; q3?: number | null; iqr?: number | null;
  percentiles?: Record<string, number | null>; skewness?: number | null; kurtosis?: number | null; warnings: string[];
}
export interface FrequencyRow {
  column: string; n_valid: number; n_missing: number; n_unique: number; ordered: boolean; mode?: string; mode_pct?: number | null;
  top: { value: string; count: number; pct: number }[]; other?: { count: number; n_categories: number } | null;
}
export interface DistributionRow {
  column: string; kind: "quantitative" | "qualitative"; n?: number;
  histogram?: { bins: { x0: number; x1: number; count: number }[]; n: number; discrete: boolean } | null;
  boxplot?: { min: number; q1: number; median: number; q3: number; max: number; whisker_low: number; whisker_high: number; outliers: number[]; n_outliers: number } | null;
  density?: { x: number[]; y: number[] } | null; frequencies?: FrequencyRow;
}
export interface CorrelationBlock {
  method: string; columns: string[]; matrix: (number | null)[][]; n_matrix: number[][]; warning: string;
  pairs: { a: string; b: string; r: number; n: number; strength: string; direction: string }[]; excluded: { column: string; reason: string }[];
}
export interface TemporalBlock {
  date_column: string; available: boolean; reason?: string; frequency: "D" | "M" | "Y"; n_dates: number; n_invalid_or_missing: number; start: string; end: string;
  count_series: { period: string; count: number }[]; gaps: string[]; n_gaps: number;
  value_series: { column: string; points: { period: string; mean: number | null; n: number }[] }[];
}
export interface TreatmentInfo {
  version_label: string; version_number: number; score_before: number | null; score_after: number | null; rows_before: number; rows_after: number;
  imputed_values: number; removed_rows: number; duplicates_resolved: number; manual_corrections: number; exceptions_accepted: number;
  operations: { label: string; column: string | null; method: string | null; affected_rows: number; justification: string | null; at: string }[];
}
export interface EdaStats {
  n_rows: number; n_columns: number; sections: string[]; skipped: Record<string, string>;
  overview: { rows: number; columns: number; type_counts: Record<string, number>; columns_info: { name: string; stat_type: string; label: string; n_valid: number; n_missing: number; pct_missing: number; n_unique: number }[] };
  descriptive?: DescriptiveRow[]; frequencies?: FrequencyRow[]; distributions?: DistributionRow[]; correlation?: CorrelationBlock;
  scatter?: { x: string; y: string; r: number; n: number; points: [number, number][] }[];
  outliers?: { column: string; method: string; available: boolean; lower?: number; upper?: number; count?: number; pct?: number; examples?: number[]; reason?: string }[];
  temporal?: TemporalBlock; missing: { columns: { column: string; n_missing: number; pct: number }[]; rows_with_missing: number; complete_rows: number };
  treatment: TreatmentInfo; observations: string[]; limitations: string[];
}
export interface EdaDetail extends EdaListItem { summary_statistics: EdaStats | null }
