import { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Database,
  Link2,
  Plus,
  RefreshCw,
  Trash2,
} from "lucide-react";
import {
  createRssFeed,
  deleteRssFeed,
  getRssFeeds,
  getRssSyncHistory,
  getRssSyncStatus,
  syncRssFeed,
  updateRssFeed,
} from "../api/client";
import type { RssFeedRecord, RssSyncResult, RssSyncRun, RssSyncStatus } from "../types";

const syncStatusLabels: Record<string, string> = {
  running: "Running",
  successful: "Successful",
  partial_success: "Partial Success",
  failed: "Failed",
};

function formatDate(value: string | null): string {
  if (!value) return "Belum pernah disinkronkan";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Waktu tidak tersedia"
    : new Intl.DateTimeFormat("id-ID", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(date);
}

function statusStyle(status: string): string {
  if (status === "successful") {
    return "border-emerald-400/20 bg-emerald-400/[0.06] text-emerald-300";
  }
  if (status === "partial_success") {
    return "border-amber-400/20 bg-amber-400/[0.06] text-amber-300";
  }
  if (status === "failed") {
    return "border-rose-400/20 bg-rose-400/[0.06] text-rose-300";
  }
  return "border-sky-400/20 bg-sky-400/[0.06] text-sky-300";
}

function runLabel(run: RssSyncRun): string {
  const trigger = run.trigger_type === "scheduled" ? "Terjadwal" : "Manual";
  return run.source_name ? `${trigger} · ${run.source_name}` : trigger;
}

export default function RssSourcesPage() {
  const [feeds, setFeeds] = useState<RssFeedRecord[]>([]);
  const [syncStatus, setSyncStatus] = useState<RssSyncStatus | null>(null);
  const [syncHistory, setSyncHistory] = useState<RssSyncRun[]>([]);
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(true);
  const [syncInfoLoading, setSyncInfoLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [busyFeedId, setBusyFeedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [syncInfoError, setSyncInfoError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadFeeds = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setFeeds(await getRssFeeds());
    } catch (loadError: unknown) {
      setError(loadError instanceof Error ? loadError.message : "Gagal memuat sumber RSS.");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadSyncInfo = useCallback(async () => {
    setSyncInfoLoading(true);
    setSyncInfoError(null);
    try {
      const [status, history] = await Promise.all([
        getRssSyncStatus(),
        getRssSyncHistory(),
      ]);
      setSyncStatus(status);
      setSyncHistory(history);
    } catch (loadError: unknown) {
      setSyncInfoError(
        loadError instanceof Error ? loadError.message : "Gagal memuat status sinkronisasi.",
      );
    } finally {
      setSyncInfoLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadFeeds();
    void loadSyncInfo();
  }, [loadFeeds, loadSyncInfo]);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      void loadSyncInfo();
    }, 30_000);
    return () => window.clearInterval(intervalId);
  }, [loadSyncInfo]);

  async function addFeed(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const feed = await createRssFeed({ name: name.trim(), url: url.trim() });
      setFeeds((current) => [...current, feed]);
      setName("");
      setUrl("");
      setNotice("Sumber tersimpan. Dataset telah dibuat; sinkronkan feed untuk mengimpor item.");
    } catch (addError: unknown) {
      setError(addError instanceof Error ? addError.message : "Gagal menambahkan sumber RSS.");
    } finally {
      setSubmitting(false);
    }
  }

  async function toggleFeed(feed: RssFeedRecord) {
    setBusyFeedId(feed.id);
    setError(null);
    try {
      const updated = await updateRssFeed(feed.id, { enabled: !feed.enabled });
      setFeeds((current) => current.map((item) => item.id === feed.id ? updated : item));
    } catch (updateError: unknown) {
      setError(updateError instanceof Error ? updateError.message : "Gagal mengubah status sumber.");
    } finally {
      setBusyFeedId(null);
    }
  }

  async function removeFeed(feed: RssFeedRecord) {
    const confirmed = window.confirm(
      `Hapus sumber “${feed.name}”? Dataset dan post yang sudah diimpor akan tetap tersedia.`,
    );
    if (!confirmed) return;
    setBusyFeedId(feed.id);
    setError(null);
    try {
      await deleteRssFeed(feed.id);
      setFeeds((current) => current.filter((item) => item.id !== feed.id));
      setNotice("Konfigurasi sumber dihapus. Dataset dan item yang sudah masuk tetap tersimpan.");
    } catch (deleteError: unknown) {
      setError(deleteError instanceof Error ? deleteError.message : "Gagal menghapus sumber.");
    } finally {
      setBusyFeedId(null);
    }
  }

  async function syncFeed(feed: RssFeedRecord) {
    setBusyFeedId(feed.id);
    setError(null);
    setNotice(null);
    try {
      const result: RssSyncResult = await syncRssFeed(feed.id);
      await Promise.all([loadFeeds(), loadSyncInfo()]);
      setNotice(
        `${feed.name}: ${result.items_inserted} item baru disimpan, ` +
          `${result.duplicates_skipped} duplikat dilewati, dan ` +
          `${result.invalid_items} item tidak valid diabaikan.`,
      );
    } catch (syncError: unknown) {
      const message = syncError instanceof Error ? syncError.message : "Sinkronisasi RSS gagal.";
      await Promise.all([loadFeeds(), loadSyncInfo()]);
      setError(message);
    } finally {
      setBusyFeedId(null);
    }
  }

  return (
    <div className="mx-auto max-w-[1440px] px-5 py-8 sm:px-8 sm:py-10">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-white">Sumber RSS</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">
          Tambahkan feed HTTPS resmi atau tepercaya. Sinkronisasi menyimpan judul, cuplikan, waktu,
          dan tautan sumber sebagai post di dataset yang dapat dipilih pada Analysis.
        </p>
      </div>

      <form onSubmit={(event) => void addFeed(event)} className="panel-card mt-7 p-5 sm:p-6">
        <div className="mb-4 flex items-center gap-2 text-sm font-medium text-slate-200">
          <Plus size={16} className="text-accent-400" />
          Tambah sumber
        </div>
        <div className="grid gap-3 md:grid-cols-[minmax(180px,0.7fr)_minmax(280px,1.3fr)_auto]">
          <label className="text-xs text-slate-400">
            Nama sumber
            <input
              required
              maxLength={200}
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Contoh: CISA Advisories"
              className="mt-2 w-full rounded-lg border border-white/[0.1] bg-navy-950 px-3 py-2.5 text-sm text-slate-100 outline-none focus:border-accent-400/50"
            />
          </label>
          <label className="text-xs text-slate-400">
            URL RSS (HTTPS)
            <input
              required
              type="url"
              maxLength={512}
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder="https://example.org/feed.xml"
              className="mt-2 w-full rounded-lg border border-white/[0.1] bg-navy-950 px-3 py-2.5 text-sm text-slate-100 outline-none focus:border-accent-400/50"
            />
          </label>
          <button
            type="submit"
            disabled={submitting}
            className="mt-auto inline-flex items-center justify-center gap-2 rounded-lg bg-accent-400 px-4 py-2.5 text-xs font-semibold text-navy-950 transition hover:bg-accent-300 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Plus size={14} />
            {submitting ? "Menyimpan…" : "Tambah RSS"}
          </button>
        </div>
        <p className="mt-3 text-[10px] leading-5 text-slate-600">
          Hanya HTTPS port standar. Feed harus berasal dari host publik. Backend tidak mengikuti
          redirect dan membatasi respons ke 4 MiB serta 100 item per sinkronisasi.
        </p>
      </form>

      <section className="panel-card mt-6 p-5 sm:p-6" aria-labelledby="sync-status-heading">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 id="sync-status-heading" className="text-sm font-semibold text-slate-200">
              Status sinkronisasi
            </h2>
            <p className="mt-1 text-[10px] text-slate-500">
              Render Cron Job ditargetkan berjalan setiap jam. Status jadwal hanya aktif setelah
              Cron Job dikonfigurasi dan diaktifkan di Render.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void loadSyncInfo()}
            disabled={syncInfoLoading}
            className="self-start rounded-lg border border-white/[0.09] p-2 text-slate-400 transition hover:bg-white/[0.05] disabled:opacity-50"
            aria-label="Muat ulang status sinkronisasi"
          >
            <RefreshCw size={14} className={syncInfoLoading ? "animate-spin" : undefined} />
          </button>
        </div>

        {syncInfoError && (
          <p className="mt-4 rounded-lg border border-rose-400/20 bg-rose-400/[0.06] p-3 text-xs text-rose-200" role="alert">
            {syncInfoError}
          </p>
        )}
        {syncInfoLoading && !syncStatus ? (
          <p className="mt-5 text-xs text-slate-500" role="status">Memuat status sinkronisasi…</p>
        ) : syncStatus && (
          <>
            <div className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <div>
                <p className="text-[10px] uppercase tracking-wide text-slate-500">Status terakhir</p>
                <p className="mt-2">
                  {syncStatus.latest_run ? (
                    <span className={`rounded-full border px-2.5 py-1 text-[10px] ${statusStyle(syncStatus.latest_run.status)}`}>
                      {syncStatusLabels[syncStatus.latest_run.status] ?? syncStatus.latest_run.status}
                    </span>
                  ) : (
                    <span className="text-xs text-slate-400">Never Synced</span>
                  )}
                </p>
                <p className="mt-2 text-[10px] text-slate-500">
                  {syncStatus.latest_run
                    ? `${runLabel(syncStatus.latest_run)} · ${formatDate(syncStatus.latest_run.completed_at ?? syncStatus.latest_run.started_at)}`
                    : "Belum ada proses sinkronisasi"}
                </p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-wide text-slate-500">Jadwal</p>
                <p className="mt-2 text-xs text-slate-200">
                  {syncStatus.schedule_enabled ? "Aktif · setiap jam" : "Belum diaktifkan di Render"}
                </p>
                <p className="mt-2 text-[10px] text-slate-500">
                  {syncStatus.next_scheduled_at
                    ? `Berikutnya (perkiraan, waktu lokal): ${formatDate(syncStatus.next_scheduled_at)}`
                    : "Waktu berikutnya tersedia setelah jadwal Render diaktifkan"}
                </p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-wide text-slate-500">Artikel terbaru</p>
                <p className="mt-2 text-xs text-slate-200">
                  {syncStatus.latest_run
                    ? `${syncStatus.latest_run.new_articles} baru · ${syncStatus.latest_run.duplicate_articles} duplikat dilewati`
                    : "Belum ada hasil"}
                </p>
                <p className="mt-2 text-[10px] text-slate-500">
                  {syncStatus.latest_run
                    ? `${syncStatus.latest_run.failed_sources} sumber gagal · ${syncStatus.latest_run.invalid_articles} item tidak valid`
                    : "Angka akan muncul setelah sinkronisasi"}
                </p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-wide text-slate-500">Sumber diproses</p>
                <p className="mt-2 text-xs text-slate-200">
                  {syncStatus.latest_run
                    ? `${syncStatus.latest_run.successful_sources}/${syncStatus.latest_run.total_sources} berhasil`
                    : "Belum ada hasil"}
                </p>
                <p className="mt-2 text-[10px] text-slate-500">
                  Pemicu: {syncStatus.latest_run ? runLabel(syncStatus.latest_run) : "—"}
                </p>
              </div>
            </div>
            {syncStatus.latest_run?.error_summary && (
              <p className="mt-4 whitespace-pre-wrap break-words rounded-lg border border-amber-400/20 bg-amber-400/[0.05] p-3 text-[10px] leading-5 text-amber-200" role="status">
                {syncStatus.latest_run.error_summary}
              </p>
            )}
          </>
        )}

        <div className="mt-6 border-t border-white/[0.07] pt-5">
          <h3 className="text-xs font-semibold text-slate-300">Riwayat sinkronisasi</h3>
          {syncInfoLoading && syncHistory.length === 0 ? (
            <p className="mt-3 text-[10px] text-slate-500">Memuat riwayat…</p>
          ) : syncHistory.length === 0 ? (
            <p className="mt-3 text-[10px] text-slate-500">Belum ada riwayat sinkronisasi.</p>
          ) : (
            <ul className="mt-3 divide-y divide-white/[0.05]">
              {syncHistory.map((run) => (
                <li key={run.id} className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex min-w-0 flex-wrap items-center gap-2">
                    <span className={`rounded-full border px-2 py-0.5 text-[9px] ${statusStyle(run.status)}`}>
                      {syncStatusLabels[run.status] ?? run.status}
                    </span>
                    <span className="text-[10px] text-slate-300">{runLabel(run)}</span>
                    <span className="text-[10px] text-slate-500">
                      {formatDate(run.completed_at ?? run.started_at)}
                    </span>
                  </div>
                  <p className="text-[10px] text-slate-500">
                    {run.new_articles} baru · {run.duplicate_articles} duplikat · {run.failed_sources} gagal
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      {error && (
        <div className="mt-4 flex items-start gap-2 rounded-xl border border-rose-400/20 bg-rose-400/[0.06] p-4 text-xs text-rose-200" role="alert">
          <AlertCircle size={16} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}
      {notice && (
        <div className="mt-4 flex items-start gap-2 rounded-xl border border-emerald-400/20 bg-emerald-400/[0.06] p-4 text-xs text-emerald-200" role="status">
          <CheckCircle2 size={16} className="mt-0.5 shrink-0" />
          <span>{notice}</span>
        </div>
      )}

      <section className="panel-card mt-6 overflow-hidden">
        <div className="flex items-center justify-between border-b border-white/[0.07] px-5 py-4 sm:px-6">
          <div>
            <h2 className="text-sm font-semibold text-slate-200">Feed terdaftar</h2>
            <p className="mt-1 text-[10px] text-slate-500">
              Menonaktifkan sumber menghentikan sinkronisasi tanpa menghapus datanya.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void loadFeeds()}
            disabled={loading}
            className="rounded-lg border border-white/[0.09] p-2 text-slate-400 transition hover:bg-white/[0.05] disabled:opacity-50"
            aria-label="Muat ulang feed"
          >
            <RefreshCw size={14} className={loading ? "animate-spin" : undefined} />
          </button>
        </div>
        {loading ? (
          <div className="flex min-h-48 items-center justify-center gap-3 text-xs text-slate-500" role="status">
            <RefreshCw size={16} className="animate-spin text-accent-400" />
            Memuat sumber RSS…
          </div>
        ) : feeds.length === 0 ? (
          <div className="flex min-h-48 flex-col items-center justify-center px-6 text-center">
            <Link2 size={23} className="text-slate-600" />
            <p className="mt-3 text-sm font-medium text-slate-300">Belum ada sumber RSS</p>
            <p className="mt-1 max-w-md text-xs leading-5 text-slate-500">
              Tambahkan feed di atas. Dataset akan dibuat saat sumber ditambahkan, kemudian diisi
              melalui sinkronisasi.
            </p>
          </div>
        ) : (
          <ul className="divide-y divide-white/[0.06]">
            {feeds.map((feed) => {
              const busy = busyFeedId === feed.id;
              return (
                <li key={feed.id} className="p-5 sm:px-6">
                  <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-sm font-medium text-slate-200">{feed.name}</h3>
                        <span className={`rounded-full border px-2 py-0.5 text-[9px] ${
                          feed.enabled
                            ? "border-emerald-400/20 bg-emerald-400/[0.06] text-emerald-300"
                            : "border-white/[0.09] bg-white/[0.03] text-slate-500"
                        }`}>
                          {feed.enabled ? "Aktif" : "Nonaktif"}
                        </span>
                        {feed.last_sync_status === "failed" && (
                          <span className="rounded-full border border-rose-400/20 bg-rose-400/[0.06] px-2 py-0.5 text-[9px] text-rose-300">
                            Sinkronisasi gagal
                          </span>
                        )}
                      </div>
                      <a
                        href={feed.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mt-1 block break-all text-[10px] text-slate-500 hover:text-accent-300"
                      >
                        {feed.url}
                      </a>
                      <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-slate-500">
                        <span className="inline-flex items-center gap-1"><Database size={11} /> {feed.dataset_name ?? feed.name}</span>
                        <span>{feed.row_count.toLocaleString("id-ID")} post tersimpan</span>
                        <span>Sinkron terakhir: {formatDate(feed.last_synced_at)}</span>
                      </p>
                      {feed.last_sync_error && (
                        <p className="mt-2 break-words text-[10px] text-rose-300/80">
                          {feed.last_sync_error}
                        </p>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => void syncFeed(feed)}
                        disabled={!feed.enabled || busy}
                        className="inline-flex items-center gap-2 rounded-lg bg-accent-400/10 px-3 py-2 text-[10px] font-medium text-accent-300 transition hover:bg-accent-400/[0.16] disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        <RefreshCw size={12} className={busy ? "animate-spin" : undefined} />
                        {busy ? "Sinkronisasi…" : "Sinkronkan sekarang"}
                      </button>
                      <button
                        type="button"
                        onClick={() => void toggleFeed(feed)}
                        disabled={busy}
                        className="rounded-lg border border-white/[0.09] px-3 py-2 text-[10px] text-slate-400 transition hover:bg-white/[0.04] disabled:opacity-40"
                      >
                        {feed.enabled ? "Nonaktifkan" : "Aktifkan"}
                      </button>
                      <button
                        type="button"
                        onClick={() => void removeFeed(feed)}
                        disabled={busy}
                        className="inline-flex items-center gap-1 rounded-lg border border-rose-400/15 px-3 py-2 text-[10px] text-rose-300/80 transition hover:bg-rose-400/[0.06] disabled:opacity-40"
                      >
                        <Trash2 size={12} />
                        Hapus sumber
                      </button>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
