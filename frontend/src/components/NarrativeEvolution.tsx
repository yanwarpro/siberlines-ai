import { useMemo, useState } from "react";
import {
  ArrowRight,
  GitCompareArrows,
  NotebookPen,
  Trash2,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { createAnalystNote, deleteAnalystNote } from "../api/client";
import type {
  AnalysisContextComparison,
  AnalysisEvidence,
  AnalysisKeywordEvolution,
  AnalysisNarrative,
  AnalysisRecord,
  AnalysisTemporalEpisode,
  AnalystNote,
} from "../types";
import { getSafeSourceUrl } from "./alertPresentation";

function formatUtc(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Unknown"
    : new Intl.DateTimeFormat(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
        timeZone: "UTC",
      }).format(date);
}

function formatHourUtc(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Unknown"
    : new Intl.DateTimeFormat(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        timeZone: "UTC",
      }).format(date);
}

function formatDuration(seconds: number): string {
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const remaining = minutes % 60;
  return remaining ? `${hours} hr ${remaining} min` : `${hours} hr`;
}

const STATUS_STYLES: Record<string, string> = {
  new: "border-emerald-400/20 bg-emerald-400/[0.06] text-emerald-300",
  disappeared: "border-white/[0.08] bg-white/[0.02] text-slate-500 line-through",
  recurring: "border-sky-400/20 bg-sky-400/[0.06] text-sky-300",
  persistent: "border-white/[0.10] bg-white/[0.04] text-slate-300",
};

const EPISODE_COLORS = ["#49d6b3", "#7dd3fc", "#fbbf24", "#f472b6", "#a78bfa"];

function chartTooltipStyle() {
  return {
    background: "#0b1727",
    border: "1px solid rgba(255,255,255,0.1)",
    borderRadius: 8,
    fontSize: 11,
    color: "#e2e8f0",
  };
}

function QuotedPost({
  evidence,
  label,
}: {
  evidence: AnalysisEvidence;
  label: string;
}) {
  return (
    <div className="rounded-lg border border-white/[0.07] bg-navy-950/50 p-3">
      <p className="text-[9px] font-medium uppercase tracking-wide text-slate-500">
        {label}
      </p>
      <p className="mt-2 whitespace-pre-wrap break-words text-xs leading-5 text-slate-200">
        &ldquo;{evidence.text}&rdquo;
      </p>
      <p className="mt-2 text-[10px] text-slate-500">
        {evidence.source_id ?? "Unknown source"} · {formatUtc(evidence.timestamp)} UTC ·
        post {evidence.post_id.slice(0, 8)}
      </p>
      {getSafeSourceUrl(evidence.source_url) && (
        <a
          href={getSafeSourceUrl(evidence.source_url) ?? undefined}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-1 inline-block text-[10px] text-accent-300 hover:text-accent-200"
        >
          Open original source
        </a>
      )}
    </div>
  );
}

function KeywordEvolutionPanel({
  keyword,
  onSelectEpisode,
}: {
  keyword: AnalysisKeywordEvolution;
  onSelectEpisode: (episodeId: string) => void;
}) {
  const groups = [
    { key: "new", title: "New", terms: keyword.new_terms },
    { key: "disappeared", title: "Disappeared", terms: keyword.disappeared_terms },
    { key: "recurring", title: "Recurring", terms: keyword.recurring_terms },
    { key: "persistent", title: "Persistent", terms: keyword.persistent_terms },
  ] as const;

  return (
    <div className="rounded-lg border border-white/[0.07] bg-white/[0.02] p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
          Keyword evolution across {keyword.episode_count} episodes
        </p>
        <p className="text-[9px] text-slate-500">derived from post text only</p>
      </div>

      <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        {groups.map((group) => (
          <div key={group.key} className="rounded-md bg-white/[0.03] p-2">
            <p className="text-[9px] uppercase tracking-wide text-slate-500">
              {group.title} ({group.terms.length})
            </p>
            {group.terms.length === 0 ? (
              <p className="mt-1 text-[10px] text-slate-600">none</p>
            ) : (
              <div className="mt-1 flex flex-wrap gap-1">
                {group.terms.map((term) => (
                  <span
                    key={`${group.key}-${term}`}
                    className={`rounded-full border px-1.5 py-0.5 text-[9px] ${STATUS_STYLES[group.key]}`}
                  >
                    {term}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      <details className="mt-3 border-t border-white/[0.06] pt-2">
        <summary className="cursor-pointer text-[10px] font-medium text-slate-400 hover:text-slate-200">
          Per-term presence matrix ({keyword.terms.length} terms)
        </summary>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full min-w-[420px] text-left text-[10px]">
            <thead>
              <tr className="text-slate-500">
                <th className="pb-1 font-medium">Term</th>
                {keyword.episode_terms.map((episode) => (
                  <th
                    key={episode.episode_id}
                    className="pb-1 text-center font-medium"
                  >
                    {episode.label.replace("Episode ", "E")}
                  </th>
                ))}
                <th className="pb-1 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.05]">
              {keyword.terms.map((entry) => (
                <tr key={entry.term}>
                  <td className="py-1 text-slate-300">{entry.term}</td>
                  {entry.presence.map((present, index) => (
                    <td key={index} className="py-1 text-center">
                      <span
                        className={present ? "text-accent-300" : "text-slate-700"}
                      >
                        {present ? "●" : "·"}
                      </span>
                    </td>
                  ))}
                  <td className="py-1">
                    <span
                      className={`rounded-full border px-1.5 py-0.5 text-[9px] ${STATUS_STYLES[entry.status]}`}
                    >
                      {entry.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-2 flex flex-wrap gap-1">
          {keyword.episode_terms.map((episode) => (
            <button
              key={episode.episode_id}
              type="button"
              onClick={() => onSelectEpisode(episode.episode_id)}
              className="rounded-full border border-white/[0.08] px-2 py-0.5 text-[9px] text-slate-400 transition hover:border-accent-400/30 hover:text-accent-200"
            >
              {episode.label}
            </button>
          ))}
        </div>
      </details>

      <p className="mt-2 text-[10px] leading-5 text-slate-500">
        {keyword.explanation}
      </p>
    </div>
  );
}

function ContextComparisonPanel({
  comparisons,
}: {
  comparisons: AnalysisContextComparison[];
}) {
  return (
    <div className="rounded-lg border border-white/[0.07] bg-white/[0.02] p-3">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
        Context comparison
      </p>
      <div className="mt-3 space-y-3">
        {comparisons.map((comparison) => (
          <div
            key={comparison.comparison_id}
            className="rounded-md border border-white/[0.06] bg-navy-950/40 p-3"
          >
            <div className="flex flex-wrap items-center gap-2 text-[10px] text-slate-400">
              <span className="font-semibold text-slate-200">
                {comparison.from_label}
              </span>
              <ArrowRight size={11} className="text-slate-600" />
              <span className="font-semibold text-slate-200">
                {comparison.to_label}
              </span>
              <span className="text-slate-600">·</span>
              <span>{Math.round(comparison.term_overlap_ratio * 100)}% term overlap</span>
            </div>
            <div className="mt-2 grid gap-2 lg:grid-cols-2">
              <QuotedPost
                evidence={comparison.from_post}
                label={comparison.from_label}
              />
              <QuotedPost evidence={comparison.to_post} label={comparison.to_label} />
            </div>
            {(comparison.introduced_terms.length > 0 ||
              comparison.dropped_terms.length > 0) && (
              <div className="mt-2 flex flex-wrap gap-1">
                {comparison.introduced_terms.map((term) => (
                  <span
                    key={`i-${comparison.comparison_id}-${term}`}
                    className={`rounded-full border px-1.5 py-0.5 text-[9px] ${STATUS_STYLES.new}`}
                  >
                    + {term}
                  </span>
                ))}
                {comparison.dropped_terms.map((term) => (
                  <span
                    key={`d-${comparison.comparison_id}-${term}`}
                    className={`rounded-full border px-1.5 py-0.5 text-[9px] ${STATUS_STYLES.disappeared}`}
                  >
                    {term}
                  </span>
                ))}
              </div>
            )}
            <p className="mt-2 text-[10px] leading-5 text-slate-500">
              {comparison.explanation}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function VolumeComparisonChart({
  episodes,
}: {
  episodes: AnalysisTemporalEpisode[];
}) {
  const data = useMemo(() => {
    const hours = new Map<string, Record<string, number | string>>();
    for (const episode of episodes) {
      for (const point of episode.hourly_volume ?? []) {
        const existing = hours.get(point.timestamp) ?? {
          timestamp: point.timestamp,
          label: formatHourUtc(point.timestamp),
        };
        existing[episode.label] = point.count;
        hours.set(point.timestamp, existing);
      }
    }
    return [...hours.entries()]
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([, value]) => value);
  }, [episodes]);

  if (data.length === 0) {
    return (
      <p className="text-[10px] text-slate-500">
        Hourly volume is unavailable for these episodes.
      </p>
    );
  }

  return (
    <div className="h-52 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
          <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fill: "#64748b", fontSize: 9 }}
            stroke="rgba(255,255,255,0.08)"
            interval="preserveStartEnd"
            minTickGap={24}
          />
          <YAxis
            allowDecimals={false}
            tick={{ fill: "#64748b", fontSize: 9 }}
            stroke="rgba(255,255,255,0.08)"
          />
          <Tooltip
            contentStyle={chartTooltipStyle()}
            labelStyle={{ color: "#94a3b8", fontSize: 10 }}
          />
          <Legend wrapperStyle={{ fontSize: 10, color: "#94a3b8" }} />
          {episodes.map((episode, index) => (
            <Line
              key={episode.episode_id}
              type="monotone"
              dataKey={episode.label}
              stroke={EPISODE_COLORS[index % EPISODE_COLORS.length]}
              strokeWidth={2}
              dot={false}
              connectNulls={false}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function SourceDistributionChart({
  episodes,
}: {
  episodes: AnalysisTemporalEpisode[];
}) {
  const data = useMemo(() => {
    const sources = new Map<string, Record<string, number | string>>();
    for (const episode of episodes) {
      for (const entry of episode.source_distribution ?? []) {
        const key = entry.source_id ?? "Unknown source";
        const existing = sources.get(key) ?? { source: key };
        existing[episode.label] = entry.post_count;
        sources.set(key, existing);
      }
    }
    return [...sources.values()].sort((left, right) =>
      String(left.source).localeCompare(String(right.source)),
    );
  }, [episodes]);

  if (data.length === 0) {
    return (
      <p className="text-[10px] text-slate-500">
        Source distribution is unavailable for these episodes.
      </p>
    );
  }

  return (
    <div className="h-52 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
          <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
          <XAxis
            dataKey="source"
            tick={{ fill: "#64748b", fontSize: 9 }}
            stroke="rgba(255,255,255,0.08)"
            interval={0}
            angle={-18}
            textAnchor="end"
            height={44}
          />
          <YAxis
            allowDecimals={false}
            tick={{ fill: "#64748b", fontSize: 9 }}
            stroke="rgba(255,255,255,0.08)"
          />
          <Tooltip
            contentStyle={chartTooltipStyle()}
            labelStyle={{ color: "#94a3b8", fontSize: 10 }}
            cursor={{ fill: "rgba(255,255,255,0.03)" }}
          />
          <Legend wrapperStyle={{ fontSize: 10, color: "#94a3b8" }} />
          {episodes.map((episode, index) => (
            <Bar
              key={episode.episode_id}
              dataKey={episode.label}
              fill={EPISODE_COLORS[index % EPISODE_COLORS.length]}
              radius={[3, 3, 0, 0]}
              isAnimationActive={false}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function AnalystNotesPanel({
  analysis,
  episodes,
  selectedEpisodeId,
  onNotesChanged,
  onError,
}: {
  analysis: AnalysisRecord;
  episodes: AnalysisTemporalEpisode[];
  selectedEpisodeId: string | null;
  onNotesChanged: (notes: AnalystNote[]) => void;
  onError: (message: string | null) => void;
}) {
  const [body, setBody] = useState("");
  const [saving, setSaving] = useState(false);
  const notes = analysis.notes_json ?? [];
  const selectedEpisode =
    episodes.find((episode) => episode.episode_id === selectedEpisodeId) ?? null;

  async function submit() {
    const trimmed = body.trim();
    if (!trimmed || saving) return;
    setSaving(true);
    onError(null);
    try {
      const note = await createAnalystNote(analysis.id, {
        body: trimmed,
        episode_id: selectedEpisode?.episode_id ?? null,
        narrative_cluster_id: selectedEpisode?.narrative_cluster_id ?? null,
      });
      onNotesChanged([...notes, note]);
      setBody("");
    } catch (error: unknown) {
      onError(error instanceof Error ? error.message : "Could not save the note.");
    } finally {
      setSaving(false);
    }
  }

  async function remove(noteId: string) {
    onError(null);
    try {
      const updated = await deleteAnalystNote(analysis.id, noteId);
      onNotesChanged(updated.notes_json ?? []);
    } catch (error: unknown) {
      onError(error instanceof Error ? error.message : "Could not delete the note.");
    }
  }

  return (
    <div className="rounded-lg border border-amber-400/15 bg-amber-400/[0.04] p-3">
      <div className="flex items-center gap-2">
        <NotebookPen size={13} className="text-amber-300" />
        <p className="text-[10px] font-semibold uppercase tracking-wide text-amber-200">
          Analyst notes
        </p>
        <span className="rounded-full border border-amber-400/25 px-1.5 py-0.5 text-[9px] text-amber-200/80">
          analyst interpretation — not automated
        </span>
      </div>

      <p className="mt-2 text-[10px] leading-5 text-slate-400">
        Notes are stored with this saved analysis and are shown separately from
        automated evidence. Automated findings are never modified by notes.
      </p>

      <div className="mt-3">
        <textarea
          value={body}
          onChange={(event) => setBody(event.target.value)}
          rows={2}
          maxLength={4000}
          placeholder={
            selectedEpisode
              ? `Observation about ${selectedEpisode.label}…`
              : "Observation or hypothesis…"
          }
          className="w-full resize-y rounded-md border border-white/[0.09] bg-navy-950 px-2.5 py-2 text-xs text-slate-200 outline-none placeholder:text-slate-600 focus:border-amber-400/40"
        />
        <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
          <p className="text-[9px] text-slate-500">
            {selectedEpisode
              ? `Linked to ${selectedEpisode.label} · ${selectedEpisode.narrative_cluster_id}`
              : "Not linked to a specific episode"}
          </p>
          <button
            type="button"
            onClick={() => void submit()}
            disabled={saving || body.trim().length === 0}
            className="inline-flex h-7 items-center gap-1.5 rounded-md bg-amber-400/90 px-2.5 text-[10px] font-semibold text-navy-950 transition hover:bg-amber-300 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {saving ? "Saving…" : "Save note"}
          </button>
        </div>
      </div>

      {notes.length === 0 ? (
        <p className="mt-3 text-[10px] text-slate-500">
          No analyst notes recorded for this run.
        </p>
      ) : (
        <ul className="mt-3 divide-y divide-white/[0.06]">
          {notes.map((note) => (
            <li key={note.note_id} className="flex items-start gap-2 py-2">
              <div className="min-w-0 flex-1">
                <p className="whitespace-pre-wrap break-words text-xs leading-5 text-slate-200">
                  {note.body}
                </p>
                <p className="mt-1 text-[9px] text-slate-500">
                  {formatUtc(note.created_at)} UTC
                  {note.episode_id ? ` · ${note.episode_id}` : " · cluster-level"}
                </p>
              </div>
              <button
                type="button"
                onClick={() => void remove(note.note_id)}
                aria-label="Delete note"
                className="mt-0.5 rounded p-1 text-slate-600 transition hover:text-rose-300"
              >
                <Trash2 size={12} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function NarrativeEvolutionSection({
  narratives,
  analysis,
  hasLegacyMetadata,
  onNotesChanged,
  onError,
}: {
  narratives: AnalysisNarrative[];
  analysis: AnalysisRecord;
  hasLegacyMetadata: boolean;
  onNotesChanged: (notes: AnalystNote[]) => void;
  onError: (message: string | null) => void;
}) {
  const eligible = useMemo(
    () => narratives.filter((narrative) => (narrative.episodes?.length ?? 0) > 0),
    [narratives],
  );
  const [narrativeId, setNarrativeId] = useState<string | null>(
    eligible[0]?.id ?? null,
  );

  const selected =
    eligible.find((narrative) => narrative.id === narrativeId) ?? eligible[0] ?? null;

  if (hasLegacyMetadata) {
    return (
      <p className="mt-4 rounded-lg border border-sky-400/15 bg-sky-400/[0.04] p-3 text-[10px] leading-5 text-sky-200/80">
        Legacy saved run: episode metadata was not recorded, so narrative evolution
        cannot be reconstructed for this run. Episodes are not inferred.
      </p>
    );
  }

  if (eligible.length === 0) {
    return (
      <p className="mt-4 text-xs text-slate-500">
        No narrative cluster produced temporal episodes for this run, so there is
        nothing to compare across time windows.
      </p>
    );
  }

  return (
    <div className="mt-4">
      {eligible.length > 1 && (
        <div className="flex flex-wrap gap-1.5">
          {eligible.map((narrative, index) => (
            <button
              key={narrative.id}
              type="button"
              onClick={() => setNarrativeId(narrative.id)}
              className={`rounded-full border px-2.5 py-1 text-[10px] transition ${
                narrative.id === selected?.id
                  ? "border-accent-400/40 bg-accent-400/[0.10] text-accent-200"
                  : "border-white/[0.08] text-slate-400 hover:border-white/20 hover:text-slate-200"
              }`}
            >
              Cluster {String(index + 1).padStart(2, "0")} · {narrative.label} ·{" "}
              {narrative.episodes?.length ?? 0} episodes
            </button>
          ))}
        </div>
      )}

      {selected && (
        <div className="mt-3 rounded-xl border border-white/[0.07] bg-white/[0.02] p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-[10px] font-medium uppercase tracking-wide text-slate-500">
                Selected narrative cluster
              </p>
              <p className="mt-1 text-sm font-semibold text-slate-100">
                {selected.label}
              </p>
            </div>
            <p className="text-[10px] text-slate-500">
              {selected.post_count} posts · {selected.episodes?.length ?? 0} episodes ·{" "}
              {formatUtc(selected.start_time)} – {formatUtc(selected.end_time)} UTC
            </p>
          </div>

          <NarrativeEvolution
            narrative={selected}
            analysis={analysis}
            onNotesChanged={onNotesChanged}
            onError={onError}
          />
        </div>
      )}
    </div>
  );
}

function TimelineStrip({
  episodes,
  selectedEpisodeId,
  onSelect,
}: {
  episodes: AnalysisTemporalEpisode[];
  selectedEpisodeId: string | null;
  onSelect: (episodeId: string) => void;
}) {
  const bounds = useMemo(() => {
    const starts = episodes.map((episode) =>
      new Date(episode.episode_start).getTime(),
    );
    const ends = episodes.map((episode) => new Date(episode.episode_end).getTime());
    return { min: Math.min(...starts), max: Math.max(...ends) };
  }, [episodes]);
  const span = Math.max(bounds.max - bounds.min, 1);

  return (
    <div className="rounded-lg border border-white/[0.07] bg-white/[0.02] p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
          Narrative timeline
        </p>
        <p className="text-[9px] text-slate-500">
          {formatUtc(new Date(bounds.min).toISOString())} –{" "}
          {formatUtc(new Date(bounds.max).toISOString())} UTC
        </p>
      </div>

      <div className="relative mt-3 h-14">
        <div className="absolute inset-x-0 top-6 h-px bg-white/[0.08]" />
        {episodes.map((episode, index) => {
          const start = new Date(episode.episode_start).getTime();
          const end = new Date(episode.episode_end).getTime();
          const left = ((start - bounds.min) / span) * 100;
          const width = Math.max(((end - start) / span) * 100, 1.2);
          const color = EPISODE_COLORS[index % EPISODE_COLORS.length];
          const isSelected = episode.episode_id === selectedEpisodeId;
          return (
            <button
              key={episode.episode_id}
              type="button"
              onClick={() => onSelect(episode.episode_id)}
              title={`${episode.label} · ${episode.post_count} posts · ${formatUtc(episode.episode_start)} UTC`}
              style={{
                left: `${Math.min(left, 99)}%`,
                width: `${Math.min(width, 100 - Math.min(left, 99))}%`,
                background: color,
                opacity: isSelected ? 1 : 0.45,
              }}
              className="absolute top-4 h-4 rounded-full transition hover:opacity-100"
            />
          );
        })}
      </div>

      <div className="mt-1 grid gap-1 sm:grid-cols-2 xl:grid-cols-4">
        {episodes.map((episode, index) => (
          <button
            key={`${episode.episode_id}-legend`}
            type="button"
            onClick={() => onSelect(episode.episode_id)}
            className={`flex items-center gap-1.5 rounded-md border px-2 py-1 text-left text-[9px] transition ${
              episode.episode_id === selectedEpisodeId
                ? "border-accent-400/30 bg-accent-400/[0.08] text-accent-200"
                : "border-white/[0.06] text-slate-400 hover:border-white/15"
            }`}
          >
            <span
              className="h-2 w-2 shrink-0 rounded-full"
              style={{ background: EPISODE_COLORS[index % EPISODE_COLORS.length] }}
            />
            <span className="truncate">
              {episode.label} · {episode.post_count} posts
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

export default function NarrativeEvolution({
  narrative,
  analysis,
  onNotesChanged,
  onError,
}: {
  narrative: AnalysisNarrative;
  analysis: AnalysisRecord;
  onNotesChanged: (notes: AnalystNote[]) => void;
  onError: (message: string | null) => void;
}) {
  const episodes = narrative.episodes ?? [];
  const [selectedEpisodeId, setSelectedEpisodeId] = useState<string | null>(
    episodes[0]?.episode_id ?? null,
  );

  const selectedEpisode =
    episodes.find((episode) => episode.episode_id === selectedEpisodeId) ?? null;
  const keyword = narrative.keyword_evolution ?? null;
  const comparisons = narrative.context_comparisons ?? [];

  if (episodes.length < 2) {
    return (
      <div className="mt-3 rounded-lg border border-white/[0.07] bg-white/[0.02] p-3">
        <p className="text-[10px] leading-5 text-slate-500">
          Narrative evolution requires at least two temporal episodes. This cluster has{" "}
          {episodes.length === 0
            ? "no qualifying episodes"
            : "a single episode"}
          , so cross-episode comparison is not available.
        </p>
        {episodes.length === 1 && (
          <AnalystNotesPanel
            analysis={analysis}
            episodes={episodes}
            selectedEpisodeId={selectedEpisodeId}
            onNotesChanged={onNotesChanged}
            onError={onError}
          />
        )}
      </div>
    );
  }

  return (
    <div className="mt-3 space-y-3 border-t border-white/[0.06] pt-3">
      <div className="flex items-center gap-2">
        <GitCompareArrows size={13} className="text-accent-400" />
        <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-300">
          Narrative evolution
        </p>
        <span className="text-[9px] text-slate-500">
          {episodes.length} episodes · all times UTC
        </span>
      </div>

      <TimelineStrip
        episodes={episodes}
        selectedEpisodeId={selectedEpisodeId}
        onSelect={setSelectedEpisodeId}
      />

      {selectedEpisode && (
        <div className="rounded-lg border border-accent-400/15 bg-accent-400/[0.05] p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs font-semibold text-slate-100">
              {selectedEpisode.label}
            </p>
            <p className="text-[10px] text-slate-400">
              {selectedEpisode.post_count} posts ·{" "}
              {selectedEpisode.distinct_source_count} sources ·{" "}
              {formatDuration(selectedEpisode.duration.seconds)}
            </p>
          </div>
          <div className="mt-2 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-md bg-white/[0.04] p-2">
              <p className="text-[9px] text-slate-500">Start (UTC)</p>
              <p className="mt-1 text-[10px] text-slate-200">
                {formatUtc(selectedEpisode.episode_start)}
              </p>
            </div>
            <div className="rounded-md bg-white/[0.04] p-2">
              <p className="text-[9px] text-slate-500">End (UTC)</p>
              <p className="mt-1 text-[10px] text-slate-200">
                {formatUtc(selectedEpisode.episode_end)}
              </p>
            </div>
            <div className="rounded-md bg-white/[0.04] p-2">
              <p className="text-[9px] text-slate-500">Peak hour (UTC)</p>
              <p className="mt-1 text-[10px] text-slate-200">
                {formatUtc(selectedEpisode.peak_hour)} ·{" "}
                {selectedEpisode.peak_post_count} posts
              </p>
            </div>
            <div className="rounded-md bg-white/[0.04] p-2">
              <p className="text-[9px] text-slate-500">Volume signal</p>
              <p className="mt-1 text-[10px] text-slate-200">
                {selectedEpisode.volume_spike_detected ? "overlaps spike" : "none detected"}
              </p>
            </div>
          </div>
          {selectedEpisode.representative_posts.length > 0 && (
            <div className="mt-2 grid gap-2 lg:grid-cols-2">
              {selectedEpisode.representative_posts.slice(0, 2).map((evidence) => (
                <QuotedPost
                  key={evidence.post_id}
                  evidence={evidence}
                  label={selectedEpisode.label}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {keyword ? (
        <KeywordEvolutionPanel
          keyword={keyword}
          onSelectEpisode={setSelectedEpisodeId}
        />
      ) : (
        <p className="text-[10px] text-slate-500">
          Keyword evolution is unavailable for this cluster.
        </p>
      )}

      {comparisons.length > 0 ? (
        <ContextComparisonPanel comparisons={comparisons} />
      ) : (
        <p className="text-[10px] text-slate-500">
          No consecutive episode pair had representative posts available for comparison.
        </p>
      )}

      <div className="grid gap-3 xl:grid-cols-2">
        <div className="rounded-lg border border-white/[0.07] bg-white/[0.02] p-3">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
            Observed volume by hour (UTC)
          </p>
          <p className="mt-1 text-[9px] text-slate-500">
            Raw post counts per hour, not normalized.
          </p>
          <div className="mt-2">
            <VolumeComparisonChart episodes={episodes} />
          </div>
        </div>
        <div className="rounded-lg border border-white/[0.07] bg-white/[0.02] p-3">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
            Source distribution
          </p>
          <p className="mt-1 text-[9px] text-slate-500">
            Post counts per source; shared sources do not imply coordination.
          </p>
          <div className="mt-2">
            <SourceDistributionChart episodes={episodes} />
          </div>
        </div>
      </div>

      <AnalystNotesPanel
        analysis={analysis}
        episodes={episodes}
        selectedEpisodeId={selectedEpisodeId}
        onNotesChanged={onNotesChanged}
        onError={onError}
      />

      <p className="text-[10px] leading-5 text-slate-500">
        Episode comparisons describe observable wording, volume, and source overlap
        between separate time windows. They do not establish intent, coordination,
        misinformation, or cause.
      </p>
    </div>
  );
}
