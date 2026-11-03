import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Bell,
  Clock3,
  RefreshCw,
  ShieldAlert,
  SlidersHorizontal,
  X,
} from "lucide-react";
import AlertDetailPanel from "../components/AlertDetailPanel";
import AlertTable from "../components/AlertTable";
import {
  ALERT_STATUS_LABELS,
  ALERT_STATUS_ORDER,
} from "../components/alertPresentation";
import { getAlerts, getAlertSummary, getDatasets } from "../api/client";
import type { AlertListItem, AlertStatus, AlertSummary, DatasetRecord } from "../types";

interface AlertsPageProps {
  onOpenAnalysis: (analysisId: string) => void;
}

const PAGE_SIZE = 25;

interface Filters {
  severity: string;
  status: string;
  datasetId: string;
  detectedFrom: string;
  detectedTo: string;
}

const EMPTY_FILTERS: Filters = {
  severity: "",
  status: "",
  datasetId: "",
  detectedFrom: "",
  detectedTo: "",
};

function toUtcBoundary(date: string, boundary: "start" | "end"): string | undefined {
  if (!date) return undefined;
  return boundary === "start" ? `${date}T00:00:00Z` : `${date}T23:59:59Z`;
}

function SummaryCard({
  label,
  value,
  hint,
  tone = "neutral",
}: {
  label: string;
  value: number;
  hint: string;
  tone?: "neutral" | "warn" | "danger" | "good";
}) {
  const toneClass =
    tone === "danger"
      ? "text-rose-300"
      : tone === "warn"
        ? "text-amber-300"
        : tone === "good"
          ? "text-emerald-300"
          : "text-slate-100";
  return (
    <section className="panel-card p-5">
      <p className="text-xs text-slate-500">{label}</p>
      <p className={`mt-3 text-2xl font-semibold ${toneClass}`}>{value.toLocaleString()}</p>
      <p className="mt-1 text-[10px] text-slate-600">{hint}</p>
    </section>
  );
}

export default function AlertsPage({ onOpenAnalysis }: AlertsPageProps) {
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [alerts, setAlerts] = useState<AlertListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [summary, setSummary] = useState<AlertSummary | null>(null);
  const [datasets, setDatasets] = useState<DatasetRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const [selectedAlertId, setSelectedAlertId] = useState<string | null>(null);

  const loadSummary = useCallback(async () => {
    setSummaryError(null);
    try {
      setSummary(await getAlertSummary());
    } catch (loadError: unknown) {
      setSummary(null);
      setSummaryError(
        loadError instanceof Error ? loadError.message : "Could not load the alert summary.",
      );
    }
  }, []);

  const loadAlerts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const page = await getAlerts({
        severity: filters.severity || undefined,
        status: filters.status || undefined,
        datasetId: filters.datasetId || undefined,
        detectedFrom: toUtcBoundary(filters.detectedFrom, "start"),
        detectedTo: toUtcBoundary(filters.detectedTo, "end"),
        limit: PAGE_SIZE,
        offset,
      });
      setAlerts(page.items);
      setTotal(page.total);
    } catch (loadError: unknown) {
      setAlerts([]);
      setTotal(0);
      setError(loadError instanceof Error ? loadError.message : "Could not load alerts.");
    } finally {
      setLoading(false);
    }
  }, [filters, offset]);

  useEffect(() => {
    void loadAlerts();
  }, [loadAlerts]);

  useEffect(() => {
    void loadSummary();
  }, [loadSummary]);

  useEffect(() => {
    let active = true;
    getDatasets()
      .then((records) => {
        if (active) setDatasets(records);
      })
      .catch(() => {
        // The dataset filter degrades to "all datasets"; the table error state
        // already surfaces connectivity problems.
        if (active) setDatasets([]);
      });
    return () => {
      active = false;
    };
  }, []);

  function updateFilter<K extends keyof Filters>(key: K, value: Filters[K]) {
    setFilters((current) => ({ ...current, [key]: value }));
    setOffset(0);
    setSelectedAlertId(null);
  }

  function clearFilters() {
    setFilters(EMPTY_FILTERS);
    setOffset(0);
    setSelectedAlertId(null);
  }

  const refreshAll = useCallback(() => {
    void loadAlerts();
    void loadSummary();
  }, [loadAlerts, loadSummary]);

  const activeFilterCount = useMemo(
    () => Object.values(filters).filter((value) => value !== "").length,
    [filters],
  );
  const pageStart = total === 0 ? 0 : offset + 1;
  const pageEnd = Math.min(offset + PAGE_SIZE, total);

  return (
    <div className="mx-auto max-w-[1440px] px-5 py-8 sm:px-8 sm:py-10">
      <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-white">Alerts</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
            Review signals generated by the analysis engine. Every figure is read from stored alert
            records; all timestamps are UTC.
          </p>
        </div>
        <button
          type="button"
          onClick={refreshAll}
          disabled={loading}
          className="inline-flex items-center gap-2 self-start rounded-lg border border-white/[0.09] px-3 py-2 text-xs text-slate-300 transition hover:bg-white/[0.05] disabled:opacity-50 sm:self-auto"
        >
          <RefreshCw size={13} className={loading ? "animate-spin" : undefined} />
          Refresh
        </button>
      </div>

      {summaryError && (
        <div
          className="mt-6 rounded-xl border border-amber-400/20 bg-amber-400/[0.05] p-4 text-xs text-amber-200"
          role="alert"
        >
          Summary could not be loaded: {summaryError}
        </div>
      )}

      <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <SummaryCard
          label="Total alerts"
          value={summary?.total ?? 0}
          hint="All stored findings, including closed"
        />
        <SummaryCard
          label="Pending review"
          value={summary ? summary.new + summary.pending_review + summary.under_review : 0}
          hint="New, pending, and under review"
          tone="warn"
        />
        <SummaryCard
          label="High priority"
          value={summary?.high_priority ?? 0}
          hint="Severity high or critical"
          tone="danger"
        />
        <SummaryCard
          label="Resolved"
          value={summary?.resolved ?? 0}
          hint={`${summary?.dismissed ?? 0} dismissed, retained for audit`}
          tone="good"
        />
      </div>

      <section className="panel-card mt-4 p-5 sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <SlidersHorizontal size={15} className="text-accent-400" />
            <h2 className="text-sm font-semibold text-slate-200">Filters</h2>
            {activeFilterCount > 0 && (
              <span className="rounded-full border border-accent-400/25 bg-accent-400/[0.07] px-2 py-0.5 text-[9px] font-semibold text-accent-300">
                {activeFilterCount} active
              </span>
            )}
          </div>
          {activeFilterCount > 0 && (
            <button
              type="button"
              onClick={clearFilters}
              className="inline-flex items-center gap-1.5 rounded-lg border border-white/[0.09] px-2.5 py-1.5 text-[10px] text-slate-300 transition hover:bg-white/[0.05]"
            >
              <X size={11} />
              Clear filters
            </button>
          )}
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <label className="flex flex-col gap-1.5 text-[10px] font-medium uppercase tracking-wide text-slate-500">
            Severity
            <select
              value={filters.severity}
              onChange={(event) => updateFilter("severity", event.target.value)}
              className="h-9 rounded-lg border border-white/[0.09] bg-navy-950 px-2.5 text-xs normal-case tracking-normal text-slate-200 outline-none focus:border-accent-400/50"
            >
              <option value="">All severities</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </label>
          <label className="flex flex-col gap-1.5 text-[10px] font-medium uppercase tracking-wide text-slate-500">
            Status
            <select
              value={filters.status}
              onChange={(event) => updateFilter("status", event.target.value)}
              className="h-9 rounded-lg border border-white/[0.09] bg-navy-950 px-2.5 text-xs normal-case tracking-normal text-slate-200 outline-none focus:border-accent-400/50"
            >
              <option value="">All statuses</option>
              {ALERT_STATUS_ORDER.map((status: AlertStatus) => (
                <option key={status} value={status}>
                  {ALERT_STATUS_LABELS[status]}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1.5 text-[10px] font-medium uppercase tracking-wide text-slate-500">
            Dataset
            <select
              value={filters.datasetId}
              onChange={(event) => updateFilter("datasetId", event.target.value)}
              className="h-9 rounded-lg border border-white/[0.09] bg-navy-950 px-2.5 text-xs normal-case tracking-normal text-slate-200 outline-none focus:border-accent-400/50"
            >
              <option value="">All datasets</option>
              {datasets.map((dataset) => (
                <option key={dataset.id} value={dataset.id}>
                  {dataset.name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1.5 text-[10px] font-medium uppercase tracking-wide text-slate-500">
            Detected from (UTC)
            <input
              type="date"
              value={filters.detectedFrom}
              onChange={(event) => updateFilter("detectedFrom", event.target.value)}
              className="h-9 rounded-lg border border-white/[0.09] bg-navy-950 px-2.5 text-xs normal-case tracking-normal text-slate-200 outline-none focus:border-accent-400/50"
            />
          </label>
          <label className="flex flex-col gap-1.5 text-[10px] font-medium uppercase tracking-wide text-slate-500">
            Detected to (UTC)
            <input
              type="date"
              value={filters.detectedTo}
              onChange={(event) => updateFilter("detectedTo", event.target.value)}
              className="h-9 rounded-lg border border-white/[0.09] bg-navy-950 px-2.5 text-xs normal-case tracking-normal text-slate-200 outline-none focus:border-accent-400/50"
            />
          </label>
        </div>
      </section>

      {error ? (
        <section
          className="panel-card mt-4 p-5 sm:p-6"
          role="alert"
          aria-live="polite"
        >
          <div className="flex items-start gap-3">
            <ShieldAlert size={18} className="mt-0.5 shrink-0 text-rose-400" />
            <div>
              <h2 className="text-sm font-semibold text-rose-200">Alerts could not be loaded</h2>
              <p className="mt-1 break-words text-xs leading-5 text-rose-200/75">{error}</p>
              <button
                type="button"
                onClick={refreshAll}
                className="mt-3 rounded-lg border border-white/[0.09] px-3 py-2 text-xs text-slate-300 transition hover:bg-white/[0.05]"
              >
                Retry
              </button>
            </div>
          </div>
        </section>
      ) : loading ? (
        <section
          className="panel-card mt-4 flex min-h-64 items-center justify-center gap-3 text-sm text-slate-400"
          role="status"
        >
          <RefreshCw size={17} className="animate-spin text-accent-400" />
          Loading alerts…
        </section>
      ) : (
        <section className="panel-card mt-4 p-5 sm:p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Bell size={15} className="text-accent-400" />
              <h2 className="text-sm font-semibold text-slate-200">Review signal queue</h2>
            </div>
            <p className="text-[10px] text-slate-500">
              {total === 0
                ? "No matching alerts"
                : `Showing ${pageStart}–${pageEnd} of ${total}`}
            </p>
          </div>
          <div className="mt-4">
            <AlertTable
              alerts={alerts}
              selectedAlertId={selectedAlertId}
              onSelect={(alertId) =>
                setSelectedAlertId((current) => (current === alertId ? null : alertId))
              }
              emptyTitle={
                activeFilterCount > 0 ? "No alerts match these filters" : "No alerts recorded"
              }
              emptyHint={
                activeFilterCount > 0
                  ? "Adjust or clear the filters to see other stored findings."
                  : "Run an analysis that produces a review signal to populate this dashboard."
              }
            />
          </div>
          {total > PAGE_SIZE && (
            <div className="mt-4 flex items-center justify-between gap-3">
              <button
                type="button"
                disabled={offset === 0}
                onClick={() => setOffset((current) => Math.max(0, current - PAGE_SIZE))}
                className="rounded-lg border border-white/[0.09] px-3 py-2 text-[11px] text-slate-300 transition hover:bg-white/[0.05] disabled:cursor-not-allowed disabled:opacity-40"
              >
                Previous
              </button>
              <p className="text-[10px] text-slate-500">
                Page {Math.floor(offset / PAGE_SIZE) + 1} of{" "}
                {Math.max(1, Math.ceil(total / PAGE_SIZE))}
              </p>
              <button
                type="button"
                disabled={pageEnd >= total}
                onClick={() => setOffset((current) => current + PAGE_SIZE)}
                className="rounded-lg border border-white/[0.09] px-3 py-2 text-[11px] text-slate-300 transition hover:bg-white/[0.05] disabled:cursor-not-allowed disabled:opacity-40"
              >
                Next
              </button>
            </div>
          )}
        </section>
      )}

      {selectedAlertId && (
        <div className="mt-4">
          <AlertDetailPanel
            alertId={selectedAlertId}
            onClose={() => setSelectedAlertId(null)}
            onChanged={refreshAll}
            onOpenAnalysis={onOpenAnalysis}
          />
        </div>
      )}

      <p className="mt-6 flex items-start gap-2 text-[10px] leading-5 text-slate-600">
        <Clock3 size={12} className="mt-0.5 shrink-0" />
        Detections are deterministic hourly-volume heuristics. A signal indicates an observed
        change in post volume and is a prompt for human review, not proof of coordination,
        misinformation, or intent.
      </p>
    </div>
  );
}
