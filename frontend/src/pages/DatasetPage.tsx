import { Database } from "lucide-react";
import type { DatasetRecord } from "../types";

const datasets: DatasetRecord[] = [];

export default function DatasetPage() {
  return (
    <div className="mx-auto max-w-[1440px] px-5 py-8 sm:px-8 sm:py-10">
      <h1 className="text-2xl font-semibold tracking-tight text-white">Datasets</h1>
      <p className="mt-2 text-sm text-slate-500">Manage authorized data collections.</p>
      <section className="panel-card mt-8 flex min-h-72 flex-col items-center justify-center p-6 text-center">
        <Database size={24} className="text-slate-600" />
        <h2 className="mt-4 text-sm font-medium text-slate-300">
          {datasets.length === 0 ? "No datasets available" : `${datasets.length} datasets`}
        </h2>
        <p className="mt-2 max-w-md text-xs leading-5 text-slate-500">
          Dataset management endpoints and import workflows are not implemented yet.
        </p>
      </section>
    </div>
  );
}
