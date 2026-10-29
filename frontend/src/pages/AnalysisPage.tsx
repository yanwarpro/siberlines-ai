import { Activity } from "lucide-react";
import type { AnalysisRecord } from "../types";

const analyses: AnalysisRecord[] = [];

export default function AnalysisPage() {
  return (
    <div className="mx-auto max-w-[1440px] px-5 py-8 sm:px-8 sm:py-10">
      <h1 className="text-2xl font-semibold tracking-tight text-white">Analysis</h1>
      <p className="mt-2 text-sm text-slate-500">Review analysis runs and their provenance.</p>
      <section className="panel-card mt-8 flex min-h-72 flex-col items-center justify-center p-6 text-center">
        <Activity size={24} className="text-slate-600" />
        <h2 className="mt-4 text-sm font-medium text-slate-300">
          {analyses.length === 0 ? "No analyses available" : `${analyses.length} analyses`}
        </h2>
        <p className="mt-2 max-w-md text-xs leading-5 text-slate-500">
          Analysis execution is intentionally not implemented; no results are being simulated.
        </p>
      </section>
    </div>
  );
}
