import type {
  AlertDetail,
  AlertListPage,
  AlertListQuery,
  AlertNoteEntry,
  AlertStatus,
  AlertSummary,
  AnalysisRecord,
  AnalystNote,
  DatasetRecord,
  HealthResponse,
} from "../types";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1").replace(
  /\/$/,
  "",
);

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { Accept: "application/json", ...init?.headers },
  });

  if (!response.ok) {
    throw new Error(await describeFailure(response));
  }

  return (await response.json()) as T;
}

async function describeFailure(response: Response): Promise<string> {
  const fallback = `API request failed (${response.status} ${response.statusText})`;
  try {
    const body: unknown = await response.json();
    if (body && typeof body === "object" && "detail" in body) {
      const { detail } = body as { detail: unknown };
      if (typeof detail === "string" && detail.trim()) return detail;
      if (Array.isArray(detail)) {
        const messages = detail
          .map((item) =>
            item && typeof item === "object" && "msg" in item
              ? String((item as { msg: unknown }).msg)
              : null,
          )
          .filter((message): message is string => Boolean(message));
        if (messages.length > 0) return messages.join("; ");
      }
    }
  } catch {
    // Body was not JSON; fall back to the status line.
  }
  return fallback;
}

function buildQuery(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === "") continue;
    search.set(key, String(value));
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

export function getDatasets(): Promise<DatasetRecord[]> {
  return request<DatasetRecord[]>("/datasets");
}

export function getDatasetAnalyses(datasetId: string): Promise<AnalysisRecord[]> {
  return request<AnalysisRecord[]>(`/datasets/${encodeURIComponent(datasetId)}/analyses`);
}

export function createDatasetAnalysis(
  datasetId: string,
  temporalGapHours: number,
): Promise<AnalysisRecord> {
  return request<AnalysisRecord>(
    `/datasets/${encodeURIComponent(datasetId)}/analyses?temporal_gap_hours=${encodeURIComponent(temporalGapHours)}`,
    { method: "POST" },
  );
}

export function getAnalysis(analysisId: string): Promise<AnalysisRecord> {
  return request<AnalysisRecord>(`/analyses/${encodeURIComponent(analysisId)}`);
}

export function createAnalystNote(
  analysisId: string,
  payload: {
    body: string;
    episode_id?: string | null;
    narrative_cluster_id?: string | null;
  },
): Promise<AnalystNote> {
  return request<AnalystNote>(
    `/analyses/${encodeURIComponent(analysisId)}/notes`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
}

export function deleteAnalystNote(
  analysisId: string,
  noteId: string,
): Promise<AnalysisRecord> {
  return request<AnalysisRecord>(
    `/analyses/${encodeURIComponent(analysisId)}/notes/${encodeURIComponent(noteId)}`,
    { method: "DELETE" },
  );
}

export function getAlerts(query: AlertListQuery = {}): Promise<AlertListPage> {
  return request<AlertListPage>(
    `/alerts${buildQuery({
      severity: query.severity,
      status: query.status,
      dataset_id: query.datasetId,
      detected_from: query.detectedFrom,
      detected_to: query.detectedTo,
      limit: query.limit,
      offset: query.offset,
    })}`,
  );
}

export function getAlertSummary(): Promise<AlertSummary> {
  return request<AlertSummary>("/alerts/summary");
}

export function getAlert(alertId: string): Promise<AlertDetail> {
  return request<AlertDetail>(`/alerts/${encodeURIComponent(alertId)}`);
}

export function updateAlertStatus(
  alertId: string,
  status: AlertStatus,
  note?: string | null,
): Promise<AlertDetail> {
  return request<AlertDetail>(`/alerts/${encodeURIComponent(alertId)}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, note: note ?? null }),
  });
}

export function createAlertNote(
  alertId: string,
  body: string,
): Promise<AlertNoteEntry> {
  return request<AlertNoteEntry>(`/alerts/${encodeURIComponent(alertId)}/notes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ body }),
  });
}
