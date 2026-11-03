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

export type AlertStatus =
  | "new"
  | "pending_review"
  | "under_review"
  | "resolved"
  | "dismissed";

export interface AlertStatusEvent {
  event_id: string;
  from_status: string;
  to_status: string;
  note: string | null;
  recorded_at: string;
  actor: string;
}

export interface AlertNoteEntry {
  note_id: string;
  body: string;
  created_at: string;
  actor: string;
}

export interface AlertRecord {
  id: string;
  analysis_id: string;
  dataset_id: string | null;
  narrative_key: string;
  narrative_cluster_id: string | null;
  episode_id: string | null;
  severity: string;
  baseline_count: number;
  observed_count: number;
  evidence_json: AnalysisEvidence[];
  explanation: string | null;
  status: string;
  detection_interval_start: string | null;
  detection_interval_end: string | null;
  detected_at: string | null;
  fingerprint: string | null;
  status_history_json: AlertStatusEvent[];
  analyst_notes_json: AlertNoteEntry[];
  created_at: string;
  updated_at: string | null;
}

export interface AlertListItem extends AlertRecord {
  dataset_name: string | null;
  analysis_created_at: string | null;
}

export type AlertDetail = AlertListItem;

export interface AlertSummary {
  total: number;
  new: number;
  pending_review: number;
  under_review: number;
  resolved: number;
  dismissed: number;
  high_priority: number;
  medium_priority: number;
  open_total: number;
}

export interface AlertListPage {
  items: AlertListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface AlertListQuery {
  severity?: string;
  status?: string;
  datasetId?: string;
  detectedFrom?: string;
  detectedTo?: string;
  limit?: number;
  offset?: number;
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

export interface AnalystNote {
  note_id: string;
  episode_id: string | null;
  narrative_cluster_id: string | null;
  body: string;
  created_at: string;
}

export interface AnalysisRecord {
  id: string;
  dataset_id: string;
  status: string;
  config_json: Record<string, unknown>;
  metrics_json: AnalysisMetrics;
  notes_json?: AnalystNote[];
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

export interface AnalysisKeywordPresence {
  term: string;
  status: "new" | "disappeared" | "recurring" | "persistent";
  first_episode_id: string;
  last_episode_id: string;
  episode_labels: string[];
  presence: boolean[];
}

export interface AnalysisKeywordEvolution {
  narrative_cluster_id: string;
  method: string;
  episode_count: number;
  episode_terms: {
    episode_id: string;
    label: string;
    terms: string[];
  }[];
  new_terms: string[];
  disappeared_terms: string[];
  recurring_terms: string[];
  persistent_terms: string[];
  terms: AnalysisKeywordPresence[];
  explanation: string;
}

export interface AnalysisContextComparison {
  comparison_id: string;
  narrative_cluster_id: string;
  from_episode_id: string;
  to_episode_id: string;
  from_label: string;
  to_label: string;
  from_post: AnalysisEvidence;
  to_post: AnalysisEvidence;
  shared_terms: string[];
  introduced_terms: string[];
  dropped_terms: string[];
  term_overlap_ratio: number;
  method: string;
  explanation: string;
}

export interface AnalysisNarrative {
  id: string;
  label: string;
  top_terms?: string[];
  post_count: number;
  mean_similarity: number;
  start_time: string;
  end_time: string;
  representative_text: string;
  evidence_post_ids?: string[];
  episodes?: AnalysisTemporalEpisode[];
  evolution?: AnalysisEpisodeTransition[];
  keyword_evolution?: AnalysisKeywordEvolution | null;
  context_comparisons?: AnalysisContextComparison[];
  unassigned_post_ids?: string[];
  evidence: AnalysisEvidence[];
}

export interface AnalysisEpisodeTransition {
  transition_id: string;
  narrative_cluster_id: string;
  from_episode_id: string;
  to_episode_id: string;
  from_label: string;
  to_label: string;
  from_episode_end: string;
  to_episode_start: string;
  gap_between_episodes_hours: number;
  from_post_count: number;
  to_post_count: number;
  post_count_delta: number;
  volume_direction: "higher" | "lower" | "unchanged";
  from_source_count: number;
  to_source_count: number;
  shared_source_count: number;
  new_source_count: number;
  shared_terms: string[];
  introduced_terms: string[];
  dropped_terms: string[];
  term_overlap_ratio: number;
  method: string;
  explanation: string;
}

export interface AnalysisTemporalEpisode {
  episode_id: string;
  narrative_cluster_id: string;
  label: string;
  episode_start: string;
  episode_end: string;
  duration: {
    seconds: number;
    hours: number;
  };
  post_count: number;
  peak_hour: string;
  peak_post_count: number;
  distinct_source_count: number;
  top_terms?: string[];
  source_ids?: string[];
  source_distribution?: { source_id: string | null; post_count: number }[];
  hourly_volume?: { timestamp: string; count: number }[];
  representative_posts: AnalysisEvidence[];
  evidence_post_ids: string[];
  temporal_gap_threshold: number;
  clustering_method: string;
  similarity_threshold: number;
  volume_spike_detected: boolean;
  evidence_sufficient: boolean;
  explanation: string;
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
    temporal_episode_count?: number;
    narrative_evolution_count?: number;
    temporal_gap_threshold_hours?: number;
    alert_count: number;
    baseline_sufficient: boolean;
    similarity_threshold: number;
  };
  trend: SignalActivityPoint[];
  narratives: AnalysisNarrative[];
  volume_review: VolumeReviewMetrics | null;
  warnings: string[];
  methodology: string;
}

export interface VolumeReviewMetrics {
  interval_start: string;
  interval_end: string;
  baseline_hours: number;
  baseline_post_count: number;
  baseline_mean: number;
  baseline_standard_deviation: number;
  required_count: number;
  observed_count: number;
  standard_score: number;
  observed_to_baseline_ratio: number;
  related_episode_ids?: string[];
  related_narrative_ids?: string[];
}
