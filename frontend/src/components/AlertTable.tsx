import { ShieldCheck } from "lucide-react";
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
            <ShieldCheck size={21} strokeWidth={1.5} />
          </div>
          <p className="mt-4 text-sm font-medium text-slate-400">{emptyTitle}</p>
          <p className="mt-1 max-w-xs text-center text-xs leading-5 text-slate-600">{emptyHint}</p>
        </div>
      </section>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[1040px] text-left text-xs">
        <caption className="sr-only">
          Review signals detected by the analysis engine. All timestamps are UTC.
        </caption>
        <thead className="text-slate-500">
          <tr className="border-b border-white/[0.07]">
            <th scope="col" className="pb-3 pr-3 font-medium">Severity</th>
            <th scope="col" className="pb-3 pr-3 font-medium">Alert</th>
            <th scope="col" className="pb-3 pr-3 font-medium">Narrative / topic</th>
            <th scope="col" className="pb-3 pr-3 font-medium">Dataset</th>
            <th scope="col" className="pb-3 pr-3 font-medium">Temporal episode</th>
            <th scope="col" className="pb-3 pr-3 font-medium">Detected (UTC)</th>
            <th scope="col" className="pb-3 pr-3 font-medium">Status</th>
            <th scope="col" className="pb-3 font-medium">Action</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/[0.06] text-slate-300">
          {alerts.map((alert) => {
            const selected = selectedAlertId === alert.id;
            return (
              <tr key={alert.id} className={selected ? "bg-amber-400/[0.05]" : undefined}>
                <td className="py-3 pr-3">
                  <span
                    className={`rounded-full border px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wide ${severityStyle(alert.severity)}`}
                  >
                    {alert.severity}
                  </span>
                </td>
                <td className="max-w-[220px] py-3 pr-3">
                  <p className="truncate font-medium text-slate-200">Hourly volume spike</p>
                  <p className="mt-0.5 truncate text-[10px] text-slate-500">
                    {alert.observed_count} observed vs {alert.baseline_count} baseline
                  </p>
                </td>
                <td className="max-w-[190px] py-3 pr-3">
                  <p className="truncate text-[11px] text-slate-300">
                    {alert.narrative_cluster_id ?? "Not linked"}
                  </p>
                  <p className="mt-0.5 truncate text-[10px] text-slate-500">
                    {alert.narrative_key}
                  </p>
                </td>
                <td className="max-w-[170px] py-3 pr-3">
                  <p className="truncate text-[11px] text-slate-300">
                    {alert.dataset_name ?? "Unavailable"}
                  </p>
                </td>
                <td className="max-w-[150px] py-3 pr-3">
                  <p className="truncate text-[11px] text-slate-300">
                    {alert.episode_id ?? "Not linked"}
                  </p>
                </td>
                <td className="whitespace-nowrap py-3 pr-3 text-[11px] text-slate-400">
                  {formatUtcTimestamp(alert.detected_at ?? alert.detection_interval_start)}
                </td>
                <td className="py-3 pr-3">
                  <span
                    className={`rounded-full border px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wide ${statusStyle(alert.status)}`}
                  >
                    {statusLabel(alert.status)}
                  </span>
                </td>
                <td className="py-3">
                  <button
                    type="button"
                    onClick={() => onSelect?.(alert.id)}
                    aria-expanded={selected}
                    className="rounded-lg border border-white/[0.09] px-2.5 py-1.5 text-[10px] text-slate-300 transition hover:bg-white/[0.05] focus-visible:outline focus-visible:outline-1 focus-visible:outline-accent-400"
                  >
                    View details
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
