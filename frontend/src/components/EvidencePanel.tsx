import { ArrowUpRight, FileSearch } from "lucide-react";
import type { EvidenceRecord } from "../types";
import { formatUtcTimestamp, getSafeSourceUrl } from "./alertPresentation";

interface EvidencePanelProps {
  evidence: EvidenceRecord[];
  onOpenAlerts?: () => void;
}

export default function EvidencePanel({ evidence, onOpenAlerts }: EvidencePanelProps) {
  return (
    <section className="panel-card min-h-[260px] overflow-hidden">
      <div className="flex items-center justify-between gap-3 border-b border-white/[0.06] px-5 py-4 sm:px-6">
        <div>
          <h2 className="text-sm font-semibold text-slate-200">Recent evidence</h2>
          <p className="mt-1 text-[10px] text-slate-500">
            Original post samples from the latest alert
          </p>
        </div>
        {evidence.length > 0 && onOpenAlerts && (
          <button
            type="button"
            onClick={onOpenAlerts}
            className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-white/[0.08] px-2.5 py-1.5 text-[10px] text-slate-400 transition hover:border-accent-400/25 hover:text-accent-300"
          >
            View alert
            <ArrowUpRight size={12} />
          </button>
        )}
      </div>
      {evidence.length === 0 ? (
        <div className="flex h-[190px] flex-col items-center justify-center px-5">
          <div className="grid h-12 w-12 place-items-center rounded-2xl border border-white/[0.07] bg-white/[0.025] text-slate-600">
            <FileSearch size={21} strokeWidth={1.5} />
          </div>
          <p className="mt-4 text-sm font-medium text-slate-400">No stored evidence yet</p>
          <p className="mt-1 max-w-xs text-center text-xs leading-5 text-slate-600">
            Evidence appears here when an alert includes original post samples.
          </p>
        </div>
      ) : (
        <ul className="divide-y divide-white/[0.06]">
          {evidence.map((item) => (
            <li key={`${item.postId ?? item.id}`} className="px-5 py-3.5 first:pt-4 last:pb-4 sm:px-6">
              <div className="flex items-start gap-3">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent-400/70" />
                <div className="min-w-0">
                  {item.alertTitle && (
                    <p className="mb-1 text-[9px] font-semibold uppercase tracking-wide text-accent-300/80">
                      {item.alertTitle}
                    </p>
                  )}
                  <p className="whitespace-pre-wrap break-words text-xs leading-5 text-slate-300">
                    {item.description}
                  </p>
                  <p className="mt-1.5 text-[10px] leading-4 text-slate-500">
                    {item.source} · {formatUtcTimestamp(item.capturedAt)}
                    {item.postId && <span className="text-slate-600"> · post {item.postId}</span>}
                  </p>
                  {getSafeSourceUrl(item.sourceUrl) && (
                    <a
                      href={getSafeSourceUrl(item.sourceUrl) ?? undefined}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-1 inline-block text-[10px] text-accent-300 hover:text-accent-200"
                    >
                      Open original source
                    </a>
                  )}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
