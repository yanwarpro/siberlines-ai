export type PageName = "overview" | "datasets" | "analysis" | "alerts";

export interface HealthResponse {
  status: string;
}

export interface Metric {
  label: string;
  value: string;
  note: string;
}

export interface SignalActivityPoint {
  timestamp: string;
  count: number;
}

export interface AlertRecord {
  id: number;
  title: string;
  severity: string;
  status: string;
  createdAt: string;
}

export interface EvidenceRecord {
  id: number;
  description: string;
  source: string;
  capturedAt: string;
}

export interface DatasetRecord {
  id: string;
  name: string;
  source_type: string;
  row_count: number;
  status: string;
  created_at: string;
}

export interface AnalysisRecord {
  id: number;
  analysisType: string;
  status: string;
  createdAt: string;
}
