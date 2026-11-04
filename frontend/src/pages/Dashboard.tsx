import { lazy, Suspense, useEffect, useState } from "react";
import { Shield } from "lucide-react";
import AlertTable from "../components/AlertTable";
import EvidencePanel from "../components/EvidencePanel";
import MetricCard from "../components/MetricCard";
import { getAlertSummary, getAlerts } from "../api/client";
import type {
  AlertListItem,
  AlertSummary,
  EvidenceRecord,
  Metric,
  SignalActivityPoint,
} from "../types";

const TrendChart = lazy(() => import("../components/TrendChart"));

interface DashboardProps {
  apiError: string | null;
  onOpenAlerts: () => void;
}

const RECENT_ALERT_LIMIT = 5;
const ALERT_PAGE_SIZE = 100;
const EVIDENCE_SAMPLE_LIMIT = 5;

function buildSignalActivity(alerts: AlertListItem[]): SignalActivityPoint[] {
  const signalsByDay = new Map<string, Set<string>>();

  for (const alert of alerts) {
    const detectedAt = alert.detected_at ?? alert.detection_interval_start;
    if (!detectedAt) continue;

    const detectedDate = new Date(detectedAt);
    if (Number.isNaN(detectedDate.getTime())) continue;

    const day = detectedDate.toISOString().slice(0, 10);
    const detectionWindow = `${alert.narrative_key}|${detectedDate.toISOString()}`;
    const signals = signalsByDay.get(day) ?? new Set<string>();
    signals.add(detectionWindow);
    signalsByDay.set(day, signals);
  }

  return [...signalsByDay.entries()]
    .sort(([firstDay], [secondDay]) => firstDay.localeCompare(secondDay))
    .map(([timestamp, signals]) => ({ timestamp, count: signals.size }));
}

function buildEvidence(alerts: AlertListItem[]): EvidenceRecord[] {
  const latestAlert = alerts.find((alert) => alert.evidence_json.length > 0);
  if (!latestAlert) return [];

  return latestAlert.evidence_json.slice(0, EVIDENCE_SAMPLE_LIMIT).map((item, index) => ({
    id: index,
    description: item.text,
    source: [latestAlert.dataset_name, item.source_id].filter(Boolean).join(" · ") || "Source unavailable",
    capturedAt: item.timestamp,
    sourceUrl: item.source_url,
    postId: item.post_id,
    alertTitle:
      latestAlert.narrative_key === "hourly_volume_spike"
        ? "Hourly volume spike"
        : latestAlert.narrative_key,
  }));
}

async function getAllAlerts(): Promise<AlertListItem[]> {
  const firstPage = await getAlerts({ limit: ALERT_PAGE_SIZE, offset: 0 });
  const alerts = [...firstPage.items];

  for (let offset = firstPage.limit; offset < firstPage.total; offset += ALERT_PAGE_SIZE) {
    const page = await getAlerts({ limit: ALERT_PAGE_SIZE, offset });
    alerts.push(...page.items);
  }

  return alerts;
}

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
  const [signalActivity, setSignalActivity] = useState<SignalActivityPoint[]>([]);
  const [evidence, setEvidence] = useState<EvidenceRecord[]>([]);
  const [overviewError, setOverviewError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setOverviewError(null);
    Promise.all([getAlertSummary(), getAllAlerts()])
      .then(([summaryRecord, alertRecords]) => {
        if (!active) return;
        setSummary(summaryRecord);
        setRecentAlerts(alertRecords.slice(0, RECENT_ALERT_LIMIT));
        setSignalActivity(buildSignalActivity(alertRecords));
        setEvidence(buildEvidence(alertRecords));
      })
      .catch((loadError: unknown) => {
        if (!active) return;
        setSummary(null);
        setRecentAlerts([]);
        setSignalActivity([]);
        setEvidence([]);
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
          <TrendChart data={signalActivity} />
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
        <EvidencePanel evidence={evidence} onOpenAlerts={onOpenAlerts} />
      </div>
    </div>
  );
}
