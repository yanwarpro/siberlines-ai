import { lazy, Suspense, useEffect, useState } from "react";
import { Shield } from "lucide-react";
import AlertTable from "../components/AlertTable";
import EvidencePanel from "../components/EvidencePanel";
import MetricCard from "../components/MetricCard";
import { getAlertSummary, getAlerts } from "../api/client";
import type { AlertListItem, AlertSummary, Metric } from "../types";

const TrendChart = lazy(() => import("../components/TrendChart"));

interface DashboardProps {
  apiError: string | null;
  onOpenAlerts: () => void;
}

const RECENT_ALERT_LIMIT = 5;

function buildMetrics(summary: AlertSummary | null): Metric[] {
  if (!summary) {
    return [
      { label: "Total alerts", value: "—", note: "Summary unavailable" },
      { label: "Open alerts", value: "—", note: "Summary unavailable" },
      { label: "High priority", value: "—", note: "Summary unavailable" },
      { label: "Resolved", value: "—", note: "Summary unavailable" },
    ];
  }
  return [
    {
      label: "Total alerts",
      value: summary.total.toLocaleString(),
      note: "Stored findings",
    },
    {
      label: "Open alerts",
      value: summary.open_total.toLocaleString(),
      note: "New, pending, or under review",
    },
    {
      label: "High priority",
      value: summary.high_priority.toLocaleString(),
      note: "Severity high or critical",
    },
    {
      label: "Resolved",
      value: summary.resolved.toLocaleString(),
      note: `${summary.dismissed.toLocaleString()} dismissed`,
    },
  ];
}

export default function Dashboard({ apiError, onOpenAlerts }: DashboardProps) {
  const [summary, setSummary] = useState<AlertSummary | null>(null);
  const [recentAlerts, setRecentAlerts] = useState<AlertListItem[]>([]);
  const [overviewError, setOverviewError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setOverviewError(null);
    Promise.all([getAlertSummary(), getAlerts({ limit: RECENT_ALERT_LIMIT, offset: 0 })])
      .then(([summaryRecord, page]) => {
        if (!active) return;
        setSummary(summaryRecord);
        setRecentAlerts(page.items);
      })
      .catch((loadError: unknown) => {
        if (!active) return;
        setSummary(null);
        setRecentAlerts([]);
        setOverviewError(
          loadError instanceof Error ? loadError.message : "Alert overview could not be loaded.",
        );
      });
    return () => {
      active = false;
    };
  }, []);

  const metrics = buildMetrics(summary);

  return (
    <div className="mx-auto max-w-[1440px] px-5 py-8 sm:px-8 sm:py-10">
      <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
        <div>
          <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-accent-400/15 bg-accent-400/[0.06] px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.15em] text-accent-400">
            <Shield size={12} />
            Defensive intelligence
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-white sm:text-[30px]">
            Intelligence overview
          </h1>
          <p className="mt-2 max-w-xl text-sm leading-6 text-slate-500">
            Alert counts and the most recent review signals, read directly from stored records.
          </p>
        </div>
        <div className="flex items-center gap-2 self-start rounded-lg border border-white/[0.08] bg-white/[0.025] px-3 py-2 text-xs text-slate-400 sm:self-auto">
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              overviewError ? "bg-rose-400" : summary ? "bg-accent-400" : "bg-amber-400"
            }`}
          />
          {overviewError
            ? "Alert overview unavailable"
            : summary
              ? "Alerts connected"
              : "Loading alerts"}
        </div>
      </div>

      {apiError && (
        <div
          role="status"
          className="mt-6 rounded-lg border border-rose-400/20 bg-rose-400/[0.06] px-4 py-3 text-xs text-rose-200"
        >
          API connection unavailable: {apiError}
        </div>
      )}

      {overviewError && (
        <div
          role="alert"
          className="mt-4 rounded-lg border border-amber-400/20 bg-amber-400/[0.05] px-4 py-3 text-xs text-amber-200"
        >
          Alert overview could not be loaded: {overviewError}
        </div>
      )}

      <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric) => (
          <MetricCard key={metric.label} metric={metric} />
        ))}
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[1.65fr_1fr]">
        <Suspense
          fallback={
            <section className="panel-card flex min-h-[350px] items-center justify-center p-5 text-xs text-slate-500">
              Loading chart…
            </section>
          }
        >
          <TrendChart data={[]} />
        </Suspense>
        <AlertTable
          alerts={recentAlerts}
          onSelect={() => onOpenAlerts()}
          emptyTitle="No alerts recorded"
          emptyHint="Run an analysis that produces a review signal to populate the alert queue."
        />
      </div>

      <div className="mt-4 flex justify-end">
        <button
          type="button"
          onClick={onOpenAlerts}
          className="rounded-lg border border-white/[0.09] px-3 py-2 text-xs text-slate-300 transition hover:bg-white/[0.05]"
        >
          Open Alerts dashboard
        </button>
      </div>

      <div className="mt-4">
        <EvidencePanel evidence={[]} />
      </div>
    </div>
  );
}
