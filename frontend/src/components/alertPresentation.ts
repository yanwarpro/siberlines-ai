import type { AlertStatus } from "../types";

export const ALERT_STATUS_ORDER: AlertStatus[] = [
  "new",
  "pending_review",
  "under_review",
  "resolved",
  "dismissed",
];

export const ALERT_STATUS_LABELS: Record<AlertStatus, string> = {
  new: "New",
  pending_review: "Pending review",
  under_review: "Under review",
  resolved: "Resolved",
  dismissed: "Dismissed",
};

export const ALERT_STATUS_STYLES: Record<AlertStatus, string> = {
  new: "border-amber-400/25 bg-amber-400/[0.08] text-amber-300",
  pending_review: "border-sky-400/25 bg-sky-400/[0.08] text-sky-300",
  under_review: "border-indigo-400/25 bg-indigo-400/[0.08] text-indigo-300",
  resolved: "border-emerald-400/25 bg-emerald-400/[0.08] text-emerald-300",
  dismissed: "border-white/[0.09] bg-white/[0.03] text-slate-400",
};

export const SEVERITY_STYLES: Record<string, string> = {
  critical: "border-rose-400/30 bg-rose-400/[0.1] text-rose-300",
  high: "border-orange-400/25 bg-orange-400/[0.08] text-orange-300",
  medium: "border-amber-400/20 bg-amber-400/[0.06] text-amber-300",
  low: "border-white/[0.09] bg-white/[0.03] text-slate-400",
};

const CLOSED_STATUSES: AlertStatus[] = ["resolved", "dismissed"];

export function isAlertStatus(value: string): value is AlertStatus {
  return (ALERT_STATUS_ORDER as string[]).includes(value);
}

export function isClosedStatus(status: string): boolean {
  return isAlertStatus(status) && CLOSED_STATUSES.includes(status);
}

export function statusLabel(status: string): string {
  return isAlertStatus(status) ? ALERT_STATUS_LABELS[status] : status;
}

export function statusStyle(status: string): string {
  return isAlertStatus(status)
    ? ALERT_STATUS_STYLES[status]
    : "border-white/[0.09] bg-white/[0.03] text-slate-400";
}

export function severityStyle(severity: string): string {
  return SEVERITY_STYLES[severity.toLowerCase()] ?? SEVERITY_STYLES.low;
}

export function formatUtcTimestamp(value: string | null | undefined): string {
  if (!value) return "Unavailable";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unavailable";
  return `${new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(date)} UTC`;
}

export function formatUtcDate(value: string | null | undefined): string {
  if (!value) return "Unavailable";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unavailable";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeZone: "UTC",
  }).format(date);
}

export function getSafeSourceUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" ? url.href : null;
  } catch {
    return null;
  }
}
