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
  id: string;
  dataset_id: string;
  status: string;
  config_json: Record<string, unknown>;
  metrics_json: AnalysisMetrics;
  created_at: string;
  completed_at: string | null;
  alerts: AnalysisAlert[];
}

export interface AnalysisEvidence {
  post_id: string;
  timestamp: string;
  source_id: string | null;
  text: string;
}

export interface AnalysisNarrative {
  id: string;
  label: string;
  post_count: number;
  mean_similarity: number;
  start_time: string;
  end_time: string;
  representative_text: string;
  evidence: AnalysisEvidence[];
}

export interface AnalysisAlert {
  id: string;
  analysis_id: string;
  narrative_key: string;
  severity: string;
  baseline_count: number;
  observed_count: number;
  evidence_json: AnalysisEvidence[];
  explanation: string | null;
  status: string;
  created_at: string;
}

export interface AnalysisMetrics {
  summary: {
    post_count: number;
    start_time: string;
    end_time: string;
    narrative_group_count: number;
    alert_count: number;
    baseline_sufficient: boolean;
    similarity_threshold: number;
  };
  trend: SignalActivityPoint[];
  narratives: AnalysisNarrative[];
  warnings: string[];
  methodology: string;
}
