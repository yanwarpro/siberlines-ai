import { useCallback, useEffect, useState } from "react";
import { AlertCircle, Database, RefreshCw } from "lucide-react";
import { getDatasets } from "../api/client";
import type { DatasetRecord } from "../types";

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Unknown"
    : new Intl.DateTimeFormat(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(date);
}

export default function DatasetPage() {
  const [datasets, setDatasets] = useState<DatasetRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadDatasets = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setDatasets(await getDatasets());
    } catch (loadError: unknown) {
      setError(
        loadError instanceof Error ? loadError.message : "An unexpected error occurred.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDatasets();
  }, [loadDatasets]);

  return (
    <div className="mx-auto max-w-[1440px] px-5 py-8 sm:px-8 sm:py-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-white">Datasets</h1>
          <p className="mt-2 text-sm text-slate-500">Manage authorized data collections.</p>
        </div>
        <button
          type="button"
          onClick={() => void loadDatasets()}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-lg border border-white/[0.09] px-3 py-2 text-xs font-medium text-slate-300 transition hover:bg-white/[0.05] disabled:cursor-not-allowed disabled:opacity-50"
        >
          <RefreshCw size={14} className={loading ? "animate-spin" : undefined} />
          Refresh
        </button>
      </div>

      <section className="panel-card mt-8 overflow-hidden">
        {loading ? (
          <div className="flex min-h-64 flex-col items-center justify-center p-6 text-center" role="status">
            <RefreshCw size={22} className="animate-spin text-accent-400" />
            <p className="mt-4 text-sm text-slate-400">Loading datasets…</p>
          </div>
        ) : error ? (
          <div className="flex min-h-64 flex-col items-center justify-center p-6 text-center" role="alert">
            <AlertCircle size={24} className="text-rose-400" />
            <h2 className="mt-4 text-sm font-medium text-slate-200">Could not load datasets</h2>
            <p className="mt-2 max-w-lg break-words text-xs leading-5 text-slate-500">{error}</p>
            <p className="mt-2 max-w-lg text-xs leading-5 text-slate-500">
              Check the API connection and the deployed frontend API URL, then try again.
            </p>
            <button
              type="button"
              onClick={() => void loadDatasets()}
              className="mt-5 rounded-lg bg-accent-400/10 px-4 py-2 text-xs font-medium text-accent-400 transition hover:bg-accent-400/15"
            >
              Try again
            </button>
          </div>
        ) : datasets.length === 0 ? (
          <div className="flex min-h-64 flex-col items-center justify-center p-6 text-center">
            <Database size={24} className="text-slate-600" />
            <h2 className="mt-4 text-sm font-medium text-slate-300">No datasets available</h2>
            <p className="mt-2 max-w-md text-xs leading-5 text-slate-500">
              Uploaded datasets will appear here. CSV uploads can be sent to the dataset upload API.
            </p>
          </div>
        ) : (
          <>
            <div className="border-b border-white/[0.07] px-5 py-4">
              <h2 className="text-sm font-medium text-slate-200">
                {datasets.length} {datasets.length === 1 ? "dataset" : "datasets"}
              </h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-left text-xs">
                <thead className="bg-white/[0.02] text-[10px] uppercase tracking-[0.12em] text-slate-500">
                  <tr>
                    <th scope="col" className="px-5 py-3 font-semibold">Name</th>
                    <th scope="col" className="px-5 py-3 font-semibold">Source</th>
                    <th scope="col" className="px-5 py-3 font-semibold">Rows</th>
                    <th scope="col" className="px-5 py-3 font-semibold">Status</th>
                    <th scope="col" className="px-5 py-3 font-semibold">Created</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.05]">
                  {datasets.map((dataset) => (
                    <tr key={dataset.id} className="text-slate-300">
                      <td className="max-w-[280px] truncate px-5 py-4 font-medium text-slate-200">
                        {dataset.name}
                      </td>
                      <td className="px-5 py-4 text-slate-400">{dataset.source_type}</td>
                      <td className="px-5 py-4 tabular-nums">{dataset.row_count.toLocaleString()}</td>
                      <td className="px-5 py-4">
                        <span className="rounded-full border border-accent-400/20 bg-accent-400/[0.07] px-2.5 py-1 text-[10px] font-medium text-accent-400">
                          {dataset.status}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-5 py-4 text-slate-500">
                        {formatDate(dataset.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
