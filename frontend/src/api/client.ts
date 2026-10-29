import type { AnalysisRecord, DatasetRecord, HealthResponse } from "../types";

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
    throw new Error(`API request failed (${response.status} ${response.statusText})`);
  }

  return (await response.json()) as T;
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

export function createDatasetAnalysis(datasetId: string): Promise<AnalysisRecord> {
  return request<AnalysisRecord>(
    `/datasets/${encodeURIComponent(datasetId)}/analyses`,
    { method: "POST" },
  );
}

export function getAnalysis(analysisId: string): Promise<AnalysisRecord> {
  return request<AnalysisRecord>(`/analyses/${encodeURIComponent(analysisId)}`);
}
