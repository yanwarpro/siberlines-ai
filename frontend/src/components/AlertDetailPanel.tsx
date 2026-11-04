import { useCallback, useEffect, useState } from "react";
import {
  ArrowUpRight,
  FileSearch,
  RefreshCw,
  ShieldAlert,
  X,
} from "lucide-react";
import { createAlertNote, getAlert, updateAlertStatus } from "../api/client";
import type { AlertDetail, AlertStatus } from "../types";
import {
  ALERT_STATUS_LABELS,
  formatUtcTimestamp,
  getSafeSourceUrl,
  isAlertStatus,
  isClosedStatus,
  severityStyle,
  statusStyle,
} from "./alertPresentation";

interface AlertDetailPanelProps {
  alertId: string;
  onClose: () => void;
  onChanged: () => void;
  onOpenAnalysis: (analysisId: string) => void;
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-3">
      <p className="text-[10px] text-slate-500">{label}</p>
      <p className="mt-1 break-words text-xs font-medium text-slate-200">{value}</p>
    </div>
  );
}

export default function AlertDetailPanel({
  alertId,
  onClose,
  onChanged,
  onOpenAnalysis,
}: AlertDetailPanelProps) {
  const [alert, setAlert] = useState<AlertDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pendingStatus, setPendingStatus] = useState<AlertStatus | null>(null);
  const [noteDraft, setNoteDraft] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setAlert(await getAlert(alertId));
    } catch (loadError: unknown) {
      setAlert(null);
      setError(
        loadError instanceof Error ? loadError.message : "Could not load this alert.",
      );
    } finally {
      setLoading(false);
    }
  }, [alertId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function applyStatus(status: AlertStatus, note?: string | null) {
    setSubmitting(true);
    setActionError(null);
    try {
      setAlert(await updateAlertStatus(alertId, status, note ?? null));
      setPendingStatus(null);
      onChanged();
    } catch (actionFailure: unknown) {
      setActionError(
        actionFailure instanceof Error
          ? actionFailure.message
          : "The alert status could not be updated.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function submitNote() {
    const body = noteDraft.trim();
    if (!body) return;
    setSubmitting(true);
    setActionError(null);
    try {
      await createAlertNote(alertId, body);
      setNoteDraft("");
      await load();
      onChanged();
    } catch (actionFailure: unknown) {
      setActionError(
        actionFailure instanceof Error
          ? actionFailure.message
          : "The note could not be saved.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  const closed = alert ? isClosedStatus(alert.status) : false;

  return (
    <section className="panel-card p-5 sm:p-6" aria-labelledby="alert-detail-heading">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <ShieldAlert size={18} className="mt-0.5 shrink-0 text-amber-400" />
          <div>
            <h2 id="alert-detail-heading" className="text-sm font-semibold text-slate-200">
              Alert details
            </h2>
            <p className="mt-1 text-xs text-slate-500">
              Automated detection findings, original evidence, and analyst review record.
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close alert details"
          className="rounded-lg p-2 text-slate-500 transition hover:bg-white/5 hover:text-slate-300"
        >
          <X size={16} />
        </button>
      </div>

      {loading ? (
        <div className="flex min-h-40 items-center justify-center gap-3 text-xs text-slate-400" role="status">
          <RefreshCw size={15} className="animate-spin text-accent-400" />
          Loading alert…
        </div>
      ) : error ? (
        <div className="mt-5 rounded-xl border border-rose-400/20 bg-rose-400/[0.06] p-4 text-xs text-rose-200" role="alert">
          <p className="font-medium">Alert could not be loaded</p>
          <p className="mt-1 break-words text-rose-200/75">{error}</p>
          <button
            type="button"
            onClick={() => void load()}
            className="mt-3 rounded-lg border border-white/[0.09] px-3 py-2 text-slate-300 hover:bg-white/[0.05]"
          >
            Retry
          </button>
        </div>
      ) : alert ? (
        <div className="mt-5 space-y-5">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`rounded-full border px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wide ${severityStyle(alert.severity)}`}
            >
              {alert.severity}
            </span>
            <span
              className={`rounded-full border px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wide ${statusStyle(alert.status)}`}
            >
              {isAlertStatus(alert.status) ? ALERT_STATUS_LABELS[alert.status] : alert.status}
            </span>
            <span className="text-[10px] text-slate-500">
              Detected {formatUtcTimestamp(alert.detected_at ?? alert.detection_interval_start)}
            </span>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Field label="Observed posts" value={alert.observed_count.toLocaleString()} />
            <Field label="Baseline (posts/hour)" value={alert.baseline_count.toLocaleString()} />
            <Field
              label="Window start"
              value={formatUtcTimestamp(alert.detection_interval_start)}
            />
            <Field label="Window end" value={formatUtcTimestamp(alert.detection_interval_end)} />
          </div>

          <div>
            <h3 className="text-xs font-semibold text-slate-200">Detection reason</h3>
            <p className="mt-1 text-xs leading-5 text-slate-400">
              {alert.explanation ??
                "The automated engine recorded no explanation for this finding."}
            </p>
            <p className="mt-2 text-[10px] leading-5 text-slate-600">
              Automated finding · fingerprint {alert.fingerprint ?? "unavailable"}. This describes an
              observed volume change only; it is not evidence of coordination or intent.
            </p>
          </div>

          <div>
            <h3 className="text-xs font-semibold text-slate-200">Finding linkage</h3>
            <div className="mt-2 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <Field label="Dataset" value={alert.dataset_name ?? "Unavailable"} />
              <Field
                label="Narrative cluster"
                value={alert.narrative_cluster_id ?? "Not linked"}
              />
              <Field label="Temporal episode" value={alert.episode_id ?? "Not linked"} />
              <Field
                label="Analysis created"
                value={formatUtcTimestamp(alert.analysis_created_at)}
              />
            </div>
            <button
              type="button"
              onClick={() => onOpenAnalysis(alert.analysis_id)}
              className="mt-3 inline-flex items-center gap-2 rounded-lg border border-accent-400/25 bg-accent-400/[0.07] px-3 py-2 text-xs font-medium text-accent-300 transition hover:bg-accent-400/[0.12]"
            >
              View analysis
              <ArrowUpRight size={13} />
            </button>
          </div>

          <div>
            <h3 className="text-xs font-semibold text-slate-200">
              Original evidence ({alert.evidence_json.length} stored samples)
            </h3>
            <p className="mt-1 text-[10px] leading-5 text-slate-500">
              Stored post text with its original timestamp and source identifier. Times are UTC.
            </p>
            {alert.evidence_json.length === 0 ? (
              <div className="mt-3 flex flex-col items-center justify-center rounded-xl border border-white/[0.06] py-8 text-center">
                <FileSearch size={20} className="text-slate-600" />
                <p className="mt-3 text-xs text-slate-400">No evidence samples stored</p>
                <p className="mt-1 max-w-sm text-[10px] leading-5 text-slate-600">
                  This alert was stored without sampled posts. Nothing is reconstructed here.
                </p>
              </div>
            ) : (
              <ul className="mt-3 divide-y divide-white/[0.06]">
                {alert.evidence_json.map((item) => (
                  <li key={item.post_id} className="py-3 first:pt-0 last:pb-0">
                    <p className="whitespace-pre-wrap break-words text-xs leading-5 text-slate-300">
                      {item.text}
                    </p>
                    <p className="mt-1 text-[10px] text-slate-500">
                      {item.source_id ?? "Unknown source"} · {formatUtcTimestamp(item.timestamp)} ·
                      post {item.post_id}
                    </p>
                    {getSafeSourceUrl(item.source_url) && (
                      <a
                        href={getSafeSourceUrl(item.source_url) ?? undefined}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mt-1 inline-block text-[10px] text-accent-300 hover:text-accent-200"
                      >
                        Open original source
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4">
            <h3 className="text-xs font-semibold text-slate-200">Review actions</h3>
            {actionError && (
              <p className="mt-2 rounded-lg border border-rose-400/20 bg-rose-400/[0.06] p-2 text-[10px] text-rose-200" role="alert">
                {actionError}
              </p>
            )}
            {pendingStatus ? (
              <div className="mt-3 rounded-lg border border-amber-400/25 bg-amber-400/[0.06] p-3">
                <p className="text-xs text-amber-100">
                  {pendingStatus === "resolved"
                    ? "Mark this alert as resolved? It stays visible for auditability."
                    : "Dismiss this alert? It is preserved in the dashboard, not deleted."}
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    type="button"
                    disabled={submitting}
                    onClick={() => void applyStatus(pendingStatus)}
                    className="rounded-lg bg-amber-400 px-3 py-2 text-[11px] font-semibold text-navy-950 transition hover:bg-amber-300 disabled:opacity-50"
                  >
                    {submitting ? "Saving…" : "Confirm"}
                  </button>
                  <button
                    type="button"
                    disabled={submitting}
                    onClick={() => setPendingStatus(null)}
                    className="rounded-lg border border-white/[0.09] px-3 py-2 text-[11px] text-slate-300 hover:bg-white/[0.05] disabled:opacity-50"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={submitting || alert.status !== "new"}
                  onClick={() => void applyStatus("pending_review")}
                  className="rounded-lg border border-white/[0.09] px-3 py-2 text-[11px] text-slate-300 transition hover:bg-white/[0.05] disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Mark pending review
                </button>
                <button
                  type="button"
                  disabled={submitting || alert.status === "under_review" || closed}
                  onClick={() => void applyStatus("under_review")}
                  className="rounded-lg border border-white/[0.09] px-3 py-2 text-[11px] text-slate-300 transition hover:bg-white/[0.05] disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Start review
                </button>
                <button
                  type="button"
                  disabled={submitting || alert.status === "resolved"}
                  onClick={() => setPendingStatus("resolved")}
                  className="rounded-lg border border-emerald-400/25 bg-emerald-400/[0.07] px-3 py-2 text-[11px] text-emerald-300 transition hover:bg-emerald-400/[0.12] disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Mark resolved
                </button>
                <button
                  type="button"
                  disabled={submitting || alert.status === "dismissed"}
                  onClick={() => setPendingStatus("dismissed")}
                  className="rounded-lg border border-white/[0.09] px-3 py-2 text-[11px] text-slate-400 transition hover:bg-white/[0.05] disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Dismiss alert
                </button>
              </div>
            )}
            <p className="mt-2 text-[10px] leading-5 text-slate-600">
              Resolved and dismissed alerts are retained for auditability and remain filterable.
            </p>
          </div>

          <div>
            <h3 className="text-xs font-semibold text-slate-200">
              Analyst notes ({alert.analyst_notes_json.length})
            </h3>
            <p className="mt-1 text-[10px] leading-5 text-slate-500">
              Analyst interpretation is stored separately from the automated finding above.
            </p>
            {alert.analyst_notes_json.length === 0 ? (
              <p className="mt-2 text-xs text-slate-500">No analyst notes recorded.</p>
            ) : (
              <ul className="mt-3 space-y-2">
                {alert.analyst_notes_json.map((note) => (
                  <li
                    key={note.note_id}
                    className="rounded-lg border border-sky-400/15 bg-sky-400/[0.04] p-3"
                  >
                    <p className="whitespace-pre-wrap break-words text-xs leading-5 text-slate-200">
                      {note.body}
                    </p>
                    <p className="mt-1 text-[10px] text-slate-500">
                      Analyst note · {formatUtcTimestamp(note.created_at)}
                    </p>
                  </li>
                ))}
              </ul>
            )}
            <div className="mt-3">
              <label
                htmlFor="alert-note-input"
                className="text-[10px] font-medium uppercase tracking-wide text-slate-500"
              >
                Add analyst note
              </label>
              <textarea
                id="alert-note-input"
                value={noteDraft}
                onChange={(event) => setNoteDraft(event.target.value)}
                rows={3}
                maxLength={4000}
                placeholder="Record an observation or hypothesis. Keep it distinct from the automated finding."
                className="mt-1.5 w-full resize-y rounded-lg border border-white/[0.09] bg-navy-950 p-3 text-xs leading-5 text-slate-200 outline-none placeholder:text-slate-600 focus:border-accent-400/50"
              />
              <button
                type="button"
                disabled={submitting || !noteDraft.trim()}
                onClick={() => void submitNote()}
                className="mt-2 rounded-lg bg-accent-400 px-3 py-2 text-[11px] font-semibold text-navy-950 transition hover:bg-accent-300 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {submitting ? "Saving…" : "Save note"}
              </button>
            </div>
          </div>

          {alert.status_history_json.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-slate-200">Status history</h3>
              <ol className="mt-2 space-y-2">
                {alert.status_history_json.map((event) => (
                  <li
                    key={event.event_id}
                    className="rounded-lg border border-white/[0.06] p-3 text-[10px] text-slate-400"
                  >
                    <span className="text-slate-300">
                      {isAlertStatus(event.from_status)
                        ? ALERT_STATUS_LABELS[event.from_status]
                        : event.from_status}
                      {" → "}
                      {isAlertStatus(event.to_status)
                        ? ALERT_STATUS_LABELS[event.to_status]
                        : event.to_status}
                    </span>
                    {" · "}
                    {formatUtcTimestamp(event.recorded_at)}
                    {event.note && (
                      <span className="mt-1 block text-slate-500">{event.note}</span>
                    )}
                  </li>
                ))}
              </ol>
            </div>
          )}
        </div>
      ) : null}
    </section>
  );
}
