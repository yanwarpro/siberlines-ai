import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Clock3,
  Play,
  RefreshCw,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  createDatasetAnalysis,
  getAnalysis,
  getDatasetAnalyses,
  getDatasets,
} from "../api/client";
import type {
  AnalysisAlert,
  AnalysisEvidence,
  AnalysisMetrics,
  AnalysisRecord,
  DatasetRecord,
  VolumeReviewMetrics,
} from "../types";

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Unknown"
    : new Intl.DateTimeFormat(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
        timeZone: "UTC",
      }).format(date);
}

function EvidenceList({ evidence }: { evidence: AnalysisEvidence[] }) {
  if (evidence.length === 0) {
    return <p className="text-xs text-slate-500">No sample posts were attached.</p>;
  }
  return (
    <ul className="divide-y divide-white/[0.06]">
      {evidence.map((item) => (
        <li key={item.post_id} className="py-3 first:pt-0 last:pb-0">
          <p className="whitespace-pre-wrap break-words text-xs leading-5 text-slate-300">
            {item.text}
          </p>
          <p className="mt-1 text-[10px] text-slate-500">
            {item.source_id ?? "Unknown source"} · {formatDate(item.timestamp)}
          </p>
        </li>
      ))}
    </ul>
  );
}

function getVolumeReview(
  metrics: AnalysisMetrics | undefined,
  alert: AnalysisAlert | undefined,
): VolumeReviewMetrics | null {
  if (metrics?.volume_review) return metrics.volume_review;
  const firstEvidence = alert?.evidence_json[0];
  if (!metrics || !firstEvidence) return null;

  const timestamp = new Date(firstEvidence.timestamp);
  if (Number.isNaN(timestamp.getTime())) return null;
  timestamp.setUTCMinutes(0, 0, 0);
  const intervalStart = timestamp.getTime();
  const baseline = metrics.trend.filter(
    (point) => new Date(point.timestamp).getTime() < intervalStart,
  );
  if (baseline.length === 0) return null;

  const baselinePostCount = baseline.reduce((total, point) => total + point.count, 0);
  const baselineMean = baselinePostCount / baseline.length;
  const variance =
    baseline.reduce((total, point) => total + (point.count - baselineMean) ** 2, 0) /
    baseline.length;
  const standardDeviation = Math.sqrt(variance);
  const requiredCount = Math.max(
    5,
    baselineMean + 3 * standardDeviation,
    baselineMean * 2.5,
  );

  return {
    interval_start: timestamp.toISOString(),
    interval_end: new Date(intervalStart + 60 * 60 * 1000).toISOString(),
    baseline_hours: baseline.length,
    baseline_post_count: baselinePostCount,
    baseline_mean: baselineMean,
    baseline_standard_deviation: standardDeviation,
    required_count: requiredCount,
    observed_count: alert.observed_count,
    standard_score:
      (alert.observed_count - baselineMean) / Math.max(standardDeviation, 1),
    observed_to_baseline_ratio: baselineMean
      ? alert.observed_count / baselineMean
      : 0,
  };
}

export default function AnalysisPage() {
  const [datasets, setDatasets] = useState<DatasetRecord[]>([]);
  const [datasetId, setDatasetId] = useState("");
  const [analyses, setAnalyses] = useState<AnalysisRecord[]>([]);
  const [analysisId, setAnalysisId] = useState("");
  const [result, setResult] = useState<AnalysisRecord | null>(null);
  const [loadingDatasets, setLoadingDatasets] = useState(true);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [selectedSignalId, setSelectedSignalId] = useState<string | null>(null);

  const loadDatasets = useCallback(async () => {
    setLoadingDatasets(true);
    setError(null);
    try {
      const records = await getDatasets();
      setDatasets(records);
      setDatasetId((current) =>
        current && records.some((dataset) => dataset.id === current)
          ? current
          : records[0]?.id ?? "",
      );
    } catch (loadError: unknown) {
      setError(loadError instanceof Error ? loadError.message : "Could not load datasets.");
    } finally {
      setLoadingDatasets(false);
    }
  }, []);

  useEffect(() => {
    void loadDatasets();
  }, [loadDatasets]);

  useEffect(() => {
    if (!datasetId) {
      setAnalyses([]);
      setAnalysisId("");
      setResult(null);
      setHistoryError(null);
      return;
    }

    let active = true;
    setLoadingHistory(true);
    setHistoryError(null);
    setAnalysisId("");
    setResult(null);
    getDatasetAnalyses(datasetId)
      .then((records) => {
        if (!active) return;
        setAnalyses(records);
        if (records[0]) {
          setAnalysisId(records[0].id);
          setResult(records[0]);
        }
      })
      .catch((loadError: unknown) => {
        if (!active) return;
        setAnalyses([]);
        setHistoryError(
          loadError instanceof Error ? loadError.message : "Could not load saved analyses.",
        );
      })
      .finally(() => {
        if (active) setLoadingHistory(false);
      });

    return () => {
      active = false;
    };
  }, [datasetId]);

  async function openSavedAnalysis(id: string) {
    setAnalysisId(id);
    setError(null);
    setResult(null);
    try {
      setResult(await getAnalysis(id));
    } catch (loadError: unknown) {
      setError(loadError instanceof Error ? loadError.message : "Could not load this analysis.");
    }
  }

  async function runAnalysis() {
    if (!datasetId) return;
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const analysis = await createDatasetAnalysis(datasetId);
      setAnalyses((current) => [
        analysis,
        ...current.filter((record) => record.id !== analysis.id),
      ]);
      setAnalysisId(analysis.id);
      setResult(analysis);
    } catch (runError: unknown) {
      setError(runError instanceof Error ? runError.message : "Analysis could not be completed.");
    } finally {
      setRunning(false);
    }
  }

  const metrics = result?.metrics_json;
  const selectedDataset = datasets.find((dataset) => dataset.id === datasetId);
  const selectedSignal = result?.alerts.find((alert) => alert.id === selectedSignalId);
  const volumeReview = getVolumeReview(metrics, selectedSignal);
  const relatedNarratives =
    selectedSignal && metrics
      ? metrics.narratives
          .map((group) => {
            const alertEvidenceIds = new Set(
              selectedSignal.evidence_json.map((evidence) => evidence.post_id),
            );
            const sharedEvidenceCount = group.evidence.filter((evidence) =>
              alertEvidenceIds.has(evidence.post_id),
            ).length;
            return { group, sharedEvidenceCount };
          })
          .filter(({ sharedEvidenceCount }) => sharedEvidenceCount > 0)
      : [];
  const largestGroupSize = Math.max(
    1,
    ...((metrics?.narratives ?? []).map((group) => group.post_count)),
  );

  return (
    <div className="mx-auto max-w-[1440px] px-5 py-8 sm:px-8 sm:py-10">
      <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-end">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-white">Analysis</h1>
          <p className="mt-2 text-sm text-slate-500">
            Run reproducible text-similarity and hourly-volume checks on stored posts.
          </p>
        </div>
        <div className="flex flex-col gap-3 sm:flex-row">
          <label className="flex min-w-64 flex-col gap-1.5 text-[10px] font-medium uppercase tracking-wide text-slate-500">
            Dataset
            <select
              value={datasetId}
              onChange={(event) => setDatasetId(event.target.value)}
              disabled={loadingDatasets || datasets.length === 0 || running}
              className="h-10 rounded-lg border border-white/[0.09] bg-navy-950 px-3 text-xs normal-case tracking-normal text-slate-200 outline-none focus:border-accent-400/50 disabled:opacity-50"
            >
              {datasets.length === 0 && <option value="">No datasets available</option>}
              {datasets.map((dataset) => (
                <option key={dataset.id} value={dataset.id}>
                  {dataset.name} · {dataset.row_count.toLocaleString()} posts
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            onClick={() => void runAnalysis()}
            disabled={!datasetId || loadingDatasets || loadingHistory || running}
            className="inline-flex h-10 items-center justify-center gap-2 self-end rounded-lg bg-accent-400 px-4 text-xs font-semibold text-navy-950 transition hover:bg-accent-300 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {running ? (
              <RefreshCw size={14} className="animate-spin" />
            ) : (
              <Play size={14} fill="currentColor" />
            )}
            {running ? "Analyzing…" : "Run Analysis"}
          </button>
        </div>
      </div>

      {error && (
        <div className="mt-6 rounded-xl border border-rose-400/20 bg-rose-400/[0.06] p-4 text-xs text-rose-200" role="alert">
          <p className="font-medium">Analysis request failed</p>
          <p className="mt-1 break-words text-rose-200/75">{error}</p>
        </div>
      )}

      {historyError && (
        <div className="mt-4 rounded-xl border border-amber-400/20 bg-amber-400/[0.05] p-4 text-xs text-amber-200" role="alert">
          Saved analyses could not be loaded: {historyError}
        </div>
      )}

      {loadingDatasets ? (
        <section className="panel-card mt-8 flex min-h-64 items-center justify-center gap-3 text-sm text-slate-400" role="status">
          <RefreshCw size={17} className="animate-spin text-accent-400" />
          Loading datasets…
        </section>
      ) : datasets.length === 0 ? (
        <section className="panel-card mt-8 flex min-h-64 flex-col items-center justify-center p-6 text-center">
          <Activity size={24} className="text-slate-600" />
          <h2 className="mt-4 text-sm font-medium text-slate-300">No dataset to analyze</h2>
          <p className="mt-2 max-w-md text-xs leading-5 text-slate-500">
            Upload a CSV dataset first. Analysis runs use posts stored by the backend.
          </p>
          <button
            type="button"
            onClick={() => void loadDatasets()}
            className="mt-4 rounded-lg border border-white/[0.09] px-3 py-2 text-xs text-slate-300 hover:bg-white/[0.05]"
          >
            Retry
          </button>
        </section>
      ) : (
        <>
          {analyses.length > 0 && (
            <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
              <p className="text-xs text-slate-500">
                Dataset: <span className="text-slate-300">{selectedDataset?.name}</span>
              </p>
              <label className="flex items-center gap-2 text-xs text-slate-500">
                Saved runs
                <select
                  value={analysisId}
                  onChange={(event) => void openSavedAnalysis(event.target.value)}
                  disabled={loadingHistory || running}
                  className="max-w-[280px] rounded-lg border border-white/[0.09] bg-navy-950 px-3 py-2 text-xs text-slate-300 outline-none focus:border-accent-400/50"
                >
                  {analyses.map((analysis) => (
                    <option key={analysis.id} value={analysis.id}>
                      {formatDate(analysis.created_at)} · {analysis.status}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          )}

          {loadingHistory || running ? (
            <section className="panel-card mt-6 flex min-h-64 flex-col items-center justify-center p-6 text-center" role="status">
              <RefreshCw size={22} className="animate-spin text-accent-400" />
              <h2 className="mt-4 text-sm font-medium text-slate-300">
                {running ? "Analyzing stored posts…" : "Loading saved analysis…"}
              </h2>
              <p className="mt-2 text-xs text-slate-500">
                Similarity and volume checks are calculated by the backend.
              </p>
            </section>
          ) : !result || !metrics ? (
            <section className="panel-card mt-6 flex min-h-64 flex-col items-center justify-center p-6 text-center">
              <BarChart3 size={24} className="text-slate-600" />
              <h2 className="mt-4 text-sm font-medium text-slate-300">
                No saved analysis for this dataset
              </h2>
              <p className="mt-2 max-w-md text-xs leading-5 text-slate-500">
                Run analysis to calculate narrative similarity and hourly post volume from the stored data.
              </p>
            </section>
          ) : (
            <div className="mt-6 space-y-6">
              {metrics.warnings.map((warning) => (
                <div
                  key={warning}
                  className="rounded-xl border border-amber-400/20 bg-amber-400/[0.05] p-4 text-xs leading-5 text-amber-200"
                  role="status"
                >
                  {warning}
                </div>
              ))}

              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <section className="panel-card p-5">
                  <p className="text-xs text-slate-500">Posts analyzed</p>
                  <p className="mt-3 text-2xl font-semibold text-slate-100">
                    {metrics.summary.post_count.toLocaleString()}
                  </p>
                  <p className="mt-1 text-[10px] text-slate-600">Stored posts in selected dataset</p>
                </section>
                <section className="panel-card p-5">
                  <p className="text-xs text-slate-500">Similar text groups</p>
                  <p className="mt-3 text-2xl font-semibold text-slate-100">
                    {metrics.summary.narrative_group_count}
                  </p>
                  <p className="mt-1 text-[10px] text-slate-600">TF-IDF cosine similarity ≥ 0.24</p>
                </section>
                <section className="panel-card p-5">
                  <p className="text-xs text-slate-500">Review signals</p>
                  <p className="mt-3 text-2xl font-semibold text-slate-100">
                    {metrics.summary.alert_count}
                  </p>
                  <p className="mt-1 text-[10px] text-slate-600">Only when baseline is sufficient</p>
                </section>
                <section className="panel-card p-5">
                  <p className="text-xs text-slate-500">Observed time range</p>
                  <p className="mt-3 flex items-center gap-2 text-sm font-medium text-slate-200">
                    <Clock3 size={15} className="shrink-0 text-accent-400" />
                    {formatDate(metrics.summary.start_time)}
                  </p>
                  <p className="mt-1 text-[10px] text-slate-500">
                    through {formatDate(metrics.summary.end_time)}
                  </p>
                </section>
              </div>

              <section className="panel-card p-5 sm:p-6">
                <div>
                  <h2 className="text-sm font-semibold text-slate-200">Hourly post volume</h2>
                  <p className="mt-1 text-xs text-slate-500">
                    Counts are computed from stored post timestamps; all times are UTC.
                  </p>
                </div>
                <div className="mt-5 h-[280px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={metrics.trend}>
                      <defs>
                        <linearGradient id="analysis-volume-fill" x1="0" x2="0" y1="0" y2="1">
                          <stop offset="0%" stopColor="#49d6b3" stopOpacity={0.3} />
                          <stop offset="100%" stopColor="#49d6b3" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
                      <XAxis
                        dataKey="timestamp"
                        tick={{ fill: "#64748b", fontSize: 10 }}
                        tickFormatter={(value: string) =>
                          new Date(value).toLocaleString(undefined, {
                            month: "short",
                            day: "numeric",
                            hour: "2-digit",
                            timeZone: "UTC",
                          })
                        }
                        minTickGap={32}
                      />
                      <YAxis allowDecimals={false} tick={{ fill: "#64748b", fontSize: 10 }} />
                      <Tooltip
                        labelFormatter={(value) => formatDate(String(value))}
                        contentStyle={{
                          background: "#0b1727",
                          border: "1px solid rgba(255,255,255,0.1)",
                          borderRadius: 8,
                        }}
                      />
                      <Area
                        type="monotone"
                        dataKey="count"
                        name="Posts"
                        stroke="#49d6b3"
                        fill="url(#analysis-volume-fill)"
                        isAnimationActive={false}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </section>

              <section className="panel-card p-5 sm:p-6">
                <div className="flex items-start gap-3">
                  <Activity size={18} className="mt-0.5 shrink-0 text-accent-400" />
                  <div>
                    <h2 className="text-sm font-semibold text-slate-200">Similar text groups</h2>
                    <p className="mt-1 text-xs text-slate-500">
                      {metrics.narratives.length} patterns · up to {largestGroupSize} posts per group
                    </p>
                  </div>
                </div>
                {metrics.narratives.length === 0 ? (
                  <p className="mt-6 text-xs text-slate-500">No similar text groups met the configured threshold.</p>
                ) : (
                  <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    {metrics.narratives.map((group, index) => (
                      <article
                        key={group.id}
                        className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="text-[10px] font-medium uppercase tracking-wide text-slate-500">
                              Pattern {String(index + 1).padStart(2, "0")}
                            </p>
                            <p className="mt-1 text-2xl font-semibold tabular-nums text-slate-100">
                              {group.post_count}
                            </p>
                            <p className="text-[10px] text-slate-500">posts</p>
                          </div>
                          <div className="rounded-lg border border-accent-400/15 bg-accent-400/[0.06] px-2.5 py-2 text-right">
                            <p className="text-sm font-semibold tabular-nums text-accent-300">
                              {Math.round(group.mean_similarity * 100)}%
                            </p>
                            <p className="text-[9px] uppercase tracking-wide text-slate-500">similarity</p>
                          </div>
                        </div>
                        <div className="mt-4 space-y-3">
                          <div>
                            <div className="mb-1.5 flex justify-between text-[9px] text-slate-500">
                              <span>Relative group size</span>
                              <span>{Math.round((group.post_count / largestGroupSize) * 100)}%</span>
                            </div>
                            <div
                              className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]"
                              role="img"
                              aria-label={`${group.post_count} posts in this similarity group`}
                            >
                              <div
                                className="h-full rounded-full bg-accent-400"
                                style={{
                                  width: `${Math.max(3, (group.post_count / largestGroupSize) * 100)}%`,
                                }}
                              />
                            </div>
                          </div>
                          <div>
                            <div className="mb-1.5 flex justify-between text-[9px] text-slate-500">
                              <span>Similarity score</span>
                              <span>{group.mean_similarity.toFixed(2)}</span>
                            </div>
                            <div
                              className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]"
                              role="img"
                              aria-label={`Similarity score ${Math.round(group.mean_similarity * 100)} percent`}
                            >
                              <div
                                className="h-full rounded-full bg-sky-400"
                                style={{ width: `${Math.max(0, Math.min(100, group.mean_similarity * 100))}%` }}
                              />
                            </div>
                          </div>
                        </div>
                        <p className="mt-3 text-[10px] text-slate-500">
                          {formatDate(group.start_time)} – {formatDate(group.end_time)}
                        </p>
                        <details className="mt-3 border-t border-white/[0.06] pt-3">
                          <summary className="cursor-pointer text-[10px] font-medium text-slate-400 hover:text-slate-200">
                            View text &amp; {group.evidence.length} samples
                          </summary>
                          <p className="mt-3 text-xs leading-5 text-slate-300">
                            {group.representative_text}
                          </p>
                          <div className="mt-3">
                            <EvidenceList evidence={group.evidence} />
                          </div>
                        </details>
                      </article>
                    ))}
                  </div>
                )}
              </section>

              <section className="panel-card p-5 sm:p-6">
                <div className="flex items-start gap-3">
                  <AlertTriangle size={18} className="mt-0.5 shrink-0 text-amber-400" />
                  <div>
                    <h2 className="text-sm font-semibold text-slate-200">Volume review signals</h2>
                    <p className="mt-1 text-xs text-slate-500">
                      {result.alerts.length} detected · based on hourly volume
                    </p>
                  </div>
                </div>
                {result.alerts.length === 0 ? (
                  <p className="mt-5 text-xs text-slate-500">
                    No volume alert was created. The dataset may not have a qualifying spike or enough historical baseline.
                  </p>
                ) : (
                    <div className="mt-5 space-y-3">
                    {result.alerts.map((alert) => (
                        <button
                          key={alert.id}
                          type="button"
                          aria-expanded={selectedSignalId === alert.id}
                          onClick={() =>
                            setSelectedSignalId((current) =>
                              current === alert.id ? null : alert.id,
                            )
                          }
                          className={`w-full rounded-xl border p-4 text-left transition ${
                            selectedSignalId === alert.id
                              ? "border-amber-400/35 bg-amber-400/[0.08]"
                              : "border-amber-400/15 bg-amber-400/[0.035] hover:border-amber-400/30 hover:bg-amber-400/[0.06]"
                          }`}
                        >
                          <span className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(240px,1.3fr)_auto] md:items-center">
                            <span className="flex items-center gap-3">
                              <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-amber-400/20 bg-amber-400/[0.08] text-amber-300">
                                <AlertTriangle size={17} />
                              </span>
                              <span>
                                <span className="flex items-center gap-2">
                                  <span className="text-xs font-semibold text-slate-200">Volume spike</span>
                                  <span className="rounded-full border border-amber-400/20 px-2 py-0.5 text-[9px] font-semibold uppercase text-amber-300">
                                    {alert.severity}
                                  </span>
                                </span>
                                <span className="mt-1 block text-[10px] text-slate-500">
                                  {volumeReview
                                    ? formatDate(volumeReview.interval_start)
                                    : "Time unavailable"}
                                </span>
                              </span>
                            </span>
                            <span>
                              <span className="mb-2 flex items-center justify-between text-[9px] text-slate-500">
                                <span>Observed vs. threshold</span>
                                <span>{alert.observed_count} observed · {volumeReview?.baseline_mean.toFixed(2) ?? alert.baseline_count} baseline</span>
                              </span>
                              <span
                                className="relative block h-2 overflow-hidden rounded-full bg-white/[0.07]"
                                role="img"
                                aria-label={`${alert.observed_count} observed posts compared with threshold ${volumeReview?.required_count.toFixed(2) ?? "unavailable"} and baseline ${volumeReview?.baseline_mean.toFixed(2) ?? alert.baseline_count}`}
                              >
                                <span
                                  className="absolute inset-y-0 left-0 rounded-full bg-amber-400"
                                  style={{
                                    width: `${Math.max(
                                      2,
                                      (alert.observed_count /
                                        Math.max(alert.observed_count, volumeReview?.required_count ?? alert.observed_count)) *
                                        100,
                                    )}%`,
                                  }}
                                />
                                <span
                                  className="absolute -top-1 bottom-[-4px] w-0.5 bg-slate-100"
                                  style={{
                                    left: `${Math.min(
                                      98,
                                      ((volumeReview?.required_count ?? alert.observed_count) /
                                        Math.max(alert.observed_count, volumeReview?.required_count ?? alert.observed_count)) *
                                        100,
                                    )}%`,
                                  }}
                                  aria-hidden="true"
                                />
                              </span>
                              <span className="mt-1.5 flex justify-between text-[9px] text-slate-600">
                                <span>0</span>
                                <span>Threshold marker</span>
                              </span>
                            </span>
                            <span className="flex items-center justify-between gap-3 md:block md:text-right">
                              <span className="text-xl font-semibold tabular-nums text-amber-300">
                                {alert.observed_count}
                                <span className="ml-1 text-[10px] font-normal text-slate-500">posts</span>
                              </span>
                              <span className="block text-[10px] font-medium text-amber-300">
                                {selectedSignalId === alert.id ? "Hide details ↑" : "View details →"}
                              </span>
                            </span>
                          </span>
                        </button>
                      ))}
                    </div>
                  )}
                  {selectedSignal && (
                    <article
                      className="mt-4 rounded-xl border border-amber-400/20 bg-navy-950/70 p-4 sm:p-6"
                      aria-label="Review signal details"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-amber-300">
                            Finding detail
                          </p>
                          <h3 className="mt-2 text-base font-semibold text-slate-100">
                            Unusual hourly post volume
                          </h3>
                        </div>
                        <span className="rounded-full border border-amber-400/20 px-2.5 py-1 text-[10px] font-semibold uppercase text-amber-300">
                          {selectedSignal.severity} review signal
                        </span>
                      </div>

                      <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                        <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-3">
                          <p className="text-[10px] text-slate-500">Detected window (UTC)</p>
                          <p className="mt-1 text-xs font-medium text-slate-200">
                            {volumeReview
                              ? `${formatDate(volumeReview.interval_start)} – ${formatDate(volumeReview.interval_end)}`
                              : selectedSignal.evidence_json[0]
                                ? formatDate(selectedSignal.evidence_json[0].timestamp)
                                : "Unavailable"}
                          </p>
                        </div>
                        <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-3">
                          <p className="text-[10px] text-slate-500">Posts in window</p>
                          <p className="mt-1 text-xs font-medium text-slate-200">
                            {selectedSignal.observed_count.toLocaleString()} observed
                            {volumeReview && ` / ${volumeReview.required_count.toFixed(2)} threshold`}
                          </p>
                        </div>
                        <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-3">
                          <p className="text-[10px] text-slate-500">Historical baseline</p>
                          <p className="mt-1 text-xs font-medium text-slate-200">
                            {volumeReview
                              ? `${volumeReview.baseline_mean.toFixed(2)} posts/hour`
                              : `About ${selectedSignal.baseline_count} posts/hour`}
                          </p>
                        </div>
                        <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-3">
                          <p className="text-[10px] text-slate-500">Baseline coverage</p>
                          <p className="mt-1 text-xs font-medium text-slate-200">
                            {volumeReview
                              ? `${volumeReview.baseline_hours} hours · ${volumeReview.baseline_post_count} posts`
                              : `${metrics?.summary.baseline_sufficient ? "Sufficient" : "Unavailable"} for review`}
                          </p>
                        </div>
                      </div>

                      <div className="mt-5 space-y-3">
                        <div>
                          <h4 className="text-xs font-semibold text-slate-200">Why it was flagged</h4>
                          <p className="mt-1 text-xs leading-5 text-slate-400">
                            {selectedSignal.explanation ??
                              "The observed count exceeded the backend's historical hourly-volume thresholds."}
                          </p>
                          {volumeReview && (
                            <p className="mt-1 text-[10px] leading-5 text-slate-500">
                              {volumeReview.observed_to_baseline_ratio.toFixed(2)}× the prior hourly mean ·
                              {" "}{volumeReview.standard_score.toFixed(2)} standard-score units from baseline.
                              The threshold is the maximum of 5 posts, the baseline mean plus 3 standard
                              deviations, and 2.5× the baseline mean; the count must reach
                              {" "}{volumeReview.required_count.toFixed(2)} posts.
                            </p>
                          )}
                        </div>
                        <div>
                          <h4 className="text-xs font-semibold text-slate-200">
                            Text groups sharing evidence samples
                          </h4>
                          {relatedNarratives.length > 0 ? (
                            <>
                              <ul className="mt-2 space-y-2">
                                {relatedNarratives.map(({ group, sharedEvidenceCount }) => (
                                  <li key={group.id} className="rounded-lg border border-white/[0.06] p-3">
                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                      <span className="text-xs text-slate-200">{group.label}</span>
                                      <span className="text-[10px] text-slate-500">
                                        {group.post_count} posts · similarity {group.mean_similarity.toFixed(2)}
                                        {" · "}{sharedEvidenceCount} shared samples
                                      </span>
                                    </div>
                                    <p className="mt-1 text-xs leading-5 text-slate-400">
                                      {group.representative_text}
                                    </p>
                                  </li>
                                ))}
                              </ul>
                              <p className="mt-2 text-[10px] leading-5 text-slate-600">
                                Shared samples indicate evidence overlap only; this does not establish a causal or coordinated relationship.
                              </p>
                            </>
                          ) : (
                            <p className="mt-1 text-xs leading-5 text-slate-500">
                              No similar-text group shares sampled posts with this signal. This does not rule out other patterns in the dataset.
                            </p>
                          )}
                        </div>
                        <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-3">
                          <h4 className="text-xs font-semibold text-slate-200">
                            Evidence posts ({selectedSignal.evidence_json.length} shown)
                          </h4>
                          <p className="mb-3 mt-1 text-[10px] leading-5 text-slate-500">
                            Samples are stored post text with original timestamps and source IDs.
                          </p>
                          <EvidenceList evidence={selectedSignal.evidence_json} />
                        </div>
                        <p className="border-t border-white/[0.06] pt-3 text-[10px] leading-5 text-slate-500">
                          Limitations: this is a deterministic hourly-volume heuristic over the available historical window. Similarity and volume signals can be affected by sparse or incomplete data; they are prompts for human review, not proof of coordination, misinformation, or intent.
                        </p>
                      </div>
                    </article>
                  )}
                </section>

              <p className="text-[10px] leading-5 text-slate-600">
                Run {result.id} · Completed {result.completed_at ? formatDate(result.completed_at) : "time unavailable"}.
                {" "}{metrics.methodology}
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
