import {
  Activity,
  ArrowUpRight,
  Clock3,
  Database,
  ShieldAlert,
} from "lucide-react";
import type { AlertListItem } from "../types";
import {
  formatUtcTimestamp,
  severityStyle,
  statusLabel,
  statusStyle,
} from "./alertPresentation";

interface AlertTableProps {
  alerts: AlertListItem[];
  selectedAlertId?: string | null;
  onSelect?: (alertId: string) => void;
  emptyTitle?: string;
  emptyHint?: string;
}

function alertTitle(alert: AlertListItem): string {
  if (alert.narrative_key === "hourly_volume_spike") return "Hourly volume spike";
  return alert.narrative_key
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export default function AlertTable({
  alerts,
  selectedAlertId,
  onSelect,
  emptyTitle = "No alerts available",
  emptyHint = "Run an analysis that produces a review signal to populate this dashboard.",
}: AlertTableProps) {
  if (alerts.length === 0) {
    return (
      <section className="panel-card min-h-[260px] p-5 sm:p-6">
        <h2 className="text-sm font-semibold text-slate-200">Alerts</h2>
        <div className="flex h-[190px] flex-col items-center justify-center">
          <div className="grid h-12 w-12 place-items-center rounded-2xl border border-white/[0.07] bg-white/[0.025] text-slate-600">
            <ShieldAlert size={21} strokeWidth={1.5} />
          </div>
          <p className="mt-4 text-sm font-medium text-slate-400">{emptyTitle}</p>
          <p className="mt-1 max-w-xs text-center text-xs leading-5 text-slate-600">{emptyHint}</p>
        </div>
      </section>
    );
  }

  return (
    <div className="space-y-3">
      {alerts.map((alert) => {
        const selected = selectedAlertId === alert.id;
        const scale = Math.max(alert.observed_count, alert.baseline_count, 1);
        const observedWidth = Math.max((alert.observed_count / scale) * 100, 4);
        const baselineWidth = Math.max((alert.baseline_count / scale) * 100, 4);
        const detectedAt = alert.detected_at ?? alert.detection_interval_start;

        return (
          <article
            key={alert.id}
            className={`group overflow-hidden rounded-xl border transition ${
              selected
                ? "border-amber-400/30 bg-amber-400/[0.045]"
                : "border-white/[0.07] bg-[#0b1727]/80 hover:border-white/[0.13] hover:bg-white/[0.025]"
            }`}
          >
            <button
              type="button"
              onClick={() => onSelect?.(alert.id)}
              aria-expanded={selected}
              aria-label={`Review ${alertTitle(alert)}, ${alert.severity} priority`}
              className="w-full text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent-400 focus-visible:outline-offset-[-2px]"
            >
              <div className="flex min-h-[124px] flex-col gap-4 p-4 sm:flex-row sm:items-center sm:gap-5 sm:px-5">
                <div className="flex min-w-0 flex-1 items-start gap-3">
                  <div
                    className={`mt-0.5 grid h-10 w-10 shrink-0 place-items-center rounded-xl border ${severityStyle(alert.severity)}`}
                  >
                    <Activity size={17} strokeWidth={1.8} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={`rounded-full border px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wide ${severityStyle(alert.severity)}`}
                      >
                        {alert.severity}
                      </span>
                      <span
                        className={`rounded-full border px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wide ${statusStyle(alert.status)}`}
                      >
                        {statusLabel(alert.status)}
                      </span>
                    </div>
                    <h3 className="mt-2 truncate text-sm font-semibold text-slate-100">
                      {alertTitle(alert)}
                    </h3>
                    <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-slate-500">
                      <span className="inline-flex min-w-0 items-center gap-1.5">
                        <Database size={11} className="shrink-0 text-slate-600" />
                        <span className="max-w-[230px] truncate">
                          {alert.dataset_name ?? "Dataset unavailable"}
                        </span>
                      </span>
                      <span className="inline-flex items-center gap-1.5">
                        <Clock3 size={11} className="shrink-0 text-slate-600" />
                        {formatUtcTimestamp(detectedAt)}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-4 sm:w-[250px] sm:shrink-0">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-end justify-between gap-3">
                      <div>
                        <p className="text-[9px] font-medium uppercase tracking-[0.12em] text-slate-500">
                          Observed
                        </p>
                        <p className="mt-0.5 text-lg font-semibold tabular-nums text-slate-100">
                          {alert.observed_count.toLocaleString()}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-[9px] font-medium uppercase tracking-[0.12em] text-slate-500">
                          Baseline
                        </p>
                        <p className="mt-0.5 text-sm font-medium tabular-nums text-slate-400">
                          {alert.baseline_count.toLocaleString()}
                        </p>
                      </div>
                    </div>
                    <div className="mt-2 space-y-1.5" aria-hidden="true">
                      <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                        <div
                          className="h-full rounded-full bg-orange-400"
                          style={{ width: `${observedWidth}%` }}
                        />
                      </div>
                      <div className="h-1 overflow-hidden rounded-full bg-white/[0.04]">
                        <div
                          className="h-full rounded-full bg-slate-500"
                          style={{ width: `${baselineWidth}%` }}
                        />
                      </div>
                    </div>
                  </div>
                  <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-white/[0.08] text-slate-500 transition group-hover:border-accent-400/25 group-hover:text-accent-300">
                    <ArrowUpRight size={14} />
                  </span>
                </div>
              </div>
            </button>
          </article>
        );
      })}
    </div>
  );
}
