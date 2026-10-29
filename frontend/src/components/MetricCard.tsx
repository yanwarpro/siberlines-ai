import type { Metric } from "../types";

interface MetricCardProps {
  metric: Metric;
}

export default function MetricCard({ metric }: MetricCardProps) {
  return (
    <section className="panel-card min-h-[122px] p-5">
      <p className="text-xs font-medium text-slate-500">{metric.label}</p>
      <div className="mt-5 flex items-end justify-between">
        <span className="text-2xl font-semibold tracking-tight text-slate-300">{metric.value}</span>
        <span className="text-[10px] text-slate-600">{metric.note}</span>
      </div>
    </section>
  );
}
