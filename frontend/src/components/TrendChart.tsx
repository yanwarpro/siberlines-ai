import { Activity } from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { SignalActivityPoint } from "../types";

interface TrendChartProps {
  data: SignalActivityPoint[];
}

export default function TrendChart({ data }: TrendChartProps) {
  return (
    <section className="panel-card min-h-[350px] p-5 sm:p-6">
      <div>
        <h2 className="text-sm font-semibold text-slate-200">Signal activity</h2>
        <p className="mt-1 text-xs text-slate-500">Activity over time</p>
      </div>
      {data.length === 0 ? (
        <div className="flex h-[250px] flex-col items-center justify-center">
          <div className="grid h-12 w-12 place-items-center rounded-2xl border border-white/[0.07] bg-white/[0.025] text-slate-600">
            <Activity size={21} strokeWidth={1.5} />
          </div>
          <p className="mt-4 text-sm font-medium text-slate-400">No signal activity yet</p>
          <p className="mt-1 max-w-xs text-center text-xs leading-5 text-slate-600">
            A chart will appear when real, authorized data is available.
          </p>
        </div>
      ) : (
        <div className="mt-6 h-[250px] w-full" aria-label="Signal activity chart">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data}>
              <defs>
                <linearGradient id="signal-fill" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="0%" stopColor="#49d6b3" stopOpacity={0.28} />
                  <stop offset="100%" stopColor="#49d6b3" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
              <XAxis dataKey="timestamp" tick={{ fill: "#64748b", fontSize: 10 }} />
              <YAxis allowDecimals={false} tick={{ fill: "#64748b", fontSize: 10 }} />
              <Tooltip
                contentStyle={{
                  background: "#0b1727",
                  border: "1px solid rgba(255,255,255,0.1)",
                  borderRadius: 8,
                }}
              />
              <Area
                type="monotone"
                dataKey="count"
                stroke="#49d6b3"
                fill="url(#signal-fill)"
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </section>
  );
}
