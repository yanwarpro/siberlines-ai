import { FileSearch } from "lucide-react";
import type { EvidenceRecord } from "../types";

interface EvidencePanelProps {
  evidence: EvidenceRecord[];
}

export default function EvidencePanel({ evidence }: EvidencePanelProps) {
  return (
    <section className="panel-card min-h-[260px] p-5 sm:p-6">
      <h2 className="text-sm font-semibold text-slate-200">Evidence</h2>
      {evidence.length === 0 ? (
        <div className="flex h-[190px] flex-col items-center justify-center">
          <div className="grid h-12 w-12 place-items-center rounded-2xl border border-white/[0.07] bg-white/[0.025] text-slate-600">
            <FileSearch size={21} strokeWidth={1.5} />
          </div>
          <p className="mt-4 text-sm font-medium text-slate-400">No evidence attached</p>
          <p className="mt-1 max-w-xs text-center text-xs leading-5 text-slate-600">
            No evidence records are available in this foundation.
          </p>
        </div>
      ) : (
        <ul className="mt-4 divide-y divide-white/[0.06]">
          {evidence.map((item) => (
            <li key={item.id} className="py-3">
              <p className="text-xs text-slate-300">{item.description}</p>
              <p className="mt-1 text-[10px] text-slate-500">
                {item.source} · {item.capturedAt}
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
