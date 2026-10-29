import { lazy, Suspense } from "react";
import { Shield } from "lucide-react";
import AlertTable from "../components/AlertTable";
import EvidencePanel from "../components/EvidencePanel";
import MetricCard from "../components/MetricCard";
import type { Metric } from "../types";

const TrendChart = lazy(() => import("../components/TrendChart"));

interface DashboardProps {
  apiError: string | null;
}

const metrics: Metric[] = [
  { label: "Active signals", value: "—", note: "No analytics configured" },
  { label: "Open alerts", value: "—", note: "No alerts generated" },
  { label: "Monitored sources", value: "—", note: "No sources connected" },
  { label: "Last updated", value: "—", note: "No data available" },
];

export default function Dashboard({ apiError }: DashboardProps) {
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
            A clear view of your monitored data and emerging signals.
          </p>
        </div>
        <div className="flex items-center gap-2 self-start rounded-lg border border-white/[0.08] bg-white/[0.025] px-3 py-2 text-xs text-slate-400 sm:self-auto">
          <span className="h-1.5 w-1.5 rounded-full bg-slate-600" />
          No data sources connected
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

      <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric) => <MetricCard key={metric.label} metric={metric} />)}
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
        <AlertTable alerts={[]} />
      </div>
      <div className="mt-4">
        <EvidencePanel evidence={[]} />
      </div>
    </div>
  );
}
