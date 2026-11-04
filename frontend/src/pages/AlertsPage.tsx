import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  Bell,
  CheckCheck,
  ChevronDown,
  Clock3,
  Layers3,
  RefreshCw,
  ShieldAlert,
  SlidersHorizontal,
  X,
} from "lucide-react";
import type { ReactNode } from "react";
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
  icon,
  tone = "neutral",
}: {
  label: string;
  value: number;
  hint: string;
  icon: ReactNode;
  tone?: "neutral" | "warn" | "danger" | "good";
}) {
  const toneStyles = {
    neutral: {
      icon: "border-sky-400/20 bg-sky-400/[0.07] text-sky-300",
      number: "text-slate-100",
      glow: "from-sky-400/[0.08]",
    },
    warn: {
      icon: "border-amber-400/20 bg-amber-400/[0.07] text-amber-300",
      number: "text-amber-200",
      glow: "from-amber-400/[0.08]",
    },
    danger: {
      icon: "border-orange-400/20 bg-orange-400/[0.07] text-orange-300",
      number: "text-orange-200",
      glow: "from-orange-400/[0.08]",
    },
    good: {
      icon: "border-emerald-400/20 bg-emerald-400/[0.07] text-emerald-300",
      number: "text-emerald-200",
      glow: "from-emerald-400/[0.08]",
    },
  }[tone];

  return (
    <section className="panel-card relative overflow-hidden p-4 sm:p-5">
      <div className={`pointer-events-none absolute inset-0 bg-gradient-to-br ${toneStyles.glow} to-transparent`} />
      <div className="relative flex items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-medium uppercase tracking-[0.13em] text-slate-500">
            {label}
          </p>
          <p className={`mt-3 text-3xl font-semibold tracking-tight tabular-nums ${toneStyles.number}`}>
            {value.toLocaleString()}
          </p>
          <p className="mt-1.5 text-[10px] text-slate-500">{hint}</p>
        </div>
        <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl border ${toneStyles.icon}`}>
          {icon}
        </span>
      </div>
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
          <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-orange-400/15 bg-orange-400/[0.06] px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.15em] text-orange-300">
            <ShieldAlert size={12} />
            Signal triage
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-white sm:text-[30px]">Alerts</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
            Prioritize unusual activity, review its evidence, and record an analyst decision.
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
          hint="Stored signals"
          icon={<Layers3 size={18} />}
        />
        <SummaryCard
          label="Pending review"
          value={summary ? summary.new + summary.pending_review + summary.under_review : 0}
          hint="Needs analyst attention"
          icon={<Bell size={18} />}
          tone="warn"
        />
        <SummaryCard
          label="High priority"
          value={summary?.high_priority ?? 0}
          hint="High or critical severity"
          icon={<Activity size={18} />}
          tone="danger"
        />
        <SummaryCard
          label="Resolved"
          value={summary?.resolved ?? 0}
          hint={`${summary?.dismissed ?? 0} dismissed · retained`}
          icon={<CheckCheck size={18} />}
          tone="good"
        />
      </div>

      <details className="panel-card group mt-4 overflow-hidden">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3.5 outline-none transition hover:bg-white/[0.025] focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent-400 sm:px-5">
          <span className="flex min-w-0 items-center gap-2.5">
            <SlidersHorizontal size={15} className="shrink-0 text-accent-400" />
            <span className="text-xs font-medium text-slate-200">Refine alert list</span>
            <span className="hidden text-[10px] text-slate-500 sm:inline">
              Severity, status, dataset, and time
            </span>
            {activeFilterCount > 0 && (
              <span className="rounded-full border border-accent-400/25 bg-accent-400/[0.07] px-2 py-0.5 text-[9px] font-semibold text-accent-300">
                {activeFilterCount}
              </span>
            )}
          </span>
          <span className="flex shrink-0 items-center gap-2 text-[10px] text-slate-500">
            {activeFilterCount > 0 && (
              <span className="hidden sm:inline">{activeFilterCount} active</span>
            )}
            <ChevronDown
              size={13}
              className="transition-transform group-open:rotate-180"
            />
          </span>
        </summary>
        <div className="border-t border-white/[0.06] p-4 sm:p-5">
          <div className="mb-3 flex justify-end">
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
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
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
        </div>
      </details>

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
        <section className="panel-card mt-4 overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.06] px-4 py-4 sm:px-5">
            <div className="flex items-center gap-2">
              <div className="grid h-8 w-8 place-items-center rounded-lg border border-accent-400/15 bg-accent-400/[0.06] text-accent-300">
                <Bell size={14} />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-slate-100">Review signal queue</h2>
                <p className="mt-0.5 text-[10px] text-slate-500">
                  {total === 0
                    ? "No matching findings"
                    : `${total.toLocaleString()} stored findings · timestamps in UTC`}
                </p>
              </div>
            </div>
            {total > 0 && (
              <span className="rounded-full border border-white/[0.07] bg-white/[0.025] px-2.5 py-1 text-[10px] tabular-nums text-slate-400">
                {pageStart}–{pageEnd} / {total}
              </span>
            )}
          </div>
          <div className="p-3 sm:p-4">
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
