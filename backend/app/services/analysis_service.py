import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from app.models import Post

TOKEN_PATTERN = re.compile(r"[^\W_]{2,}", re.UNICODE)
STOP_WORDS = {
    "ada", "agar", "akan", "atau", "belum", "beredar", "bisa", "dan", "dari",
    "dengan", "di", "hari", "ini", "itu", "juga", "karena", "ke", "lebih",
    "masih", "menurut", "oleh", "pada", "para", "perlu", "saat", "sebagai",
    "serta", "sudah", "tidak", "untuk", "yang", "the", "and", "for", "from",
    "has", "have", "in", "is", "of", "on", "or", "that", "this", "to", "with",
}
SIMILARITY_THRESHOLD = 0.24
MIN_GROUP_SIZE = 2
MAX_SIMILARITY_POSTS = 2_500
MAX_CANDIDATE_PAIRS = 1_000_000
MAX_GROUP_EVIDENCE = 5
MAX_EPISODE_REPRESENTATIVES = 3
MAX_NARRATIVE_GROUPS = 8
MAX_SPIKE_EVIDENCE = 8
MIN_BASELINE_HOURS = 24
MIN_BASELINE_POSTS = 20
MIN_EPISODE_SIZE = 2
DEFAULT_TEMPORAL_GAP_HOURS = 6.0
MAX_EVOLUTION_TERMS = 5
MAX_CONTEXT_COMPARISONS = 4
EVOLUTION_METHOD = "episode_term_volume_source_delta"
KEYWORD_EVOLUTION_METHOD = "episode_term_presence_classification"
CONTEXT_COMPARISON_METHOD = "episode_representative_post_quotation"


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in TOKEN_PATTERN.findall(text.casefold())
        if token not in STOP_WORDS
    }


def _evidence(post: Post) -> dict[str, Any]:
    timestamp = _utc_timestamp(post.timestamp)
    return {
        "post_id": str(post.id),
        "timestamp": timestamp.isoformat(),
        "source_id": post.source_id,
        "text": post.text,
    }


def _utc_timestamp(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc)


def _episode_top_terms(
    segment: list[Post],
    terms_by_post_id: dict[str, set[str]],
) -> list[str]:
    counts: Counter[str] = Counter()
    for post in segment:
        counts.update(terms_by_post_id.get(str(post.id), set()))
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [term for term, _ in ranked[:MAX_EVOLUTION_TERMS]]

def _hourly_series(posts: list[Post]) -> list[dict[str, Any]]:
    if not posts:
        return []
    counts: dict[datetime, int] = defaultdict(int)
    for post in posts:
        counts[_hour_key(post.timestamp)] += 1
    first_hour = min(counts)
    last_hour = max(counts)
    series: list[dict[str, Any]] = []
    cursor = first_hour
    while cursor <= last_hour:
        series.append(
            {"timestamp": cursor.isoformat(), "count": counts.get(cursor, 0)}
        )
        cursor += timedelta(hours=1)
    return series

def _source_distribution(posts: list[Post]) -> list[dict[str, Any]]:
    counts: Counter[str | None] = Counter(post.source_id for post in posts)
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0] or ""))
    return [
        {"source_id": source_id, "post_count": count}
        for source_id, count in ranked
    ]

def _keyword_evolution(
    narrative_id: str,
    episodes: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if len(episodes) < 2:
        return None

    episode_terms = [
        {
            "episode_id": episode["episode_id"],
            "label": episode["label"],
            "terms": list(episode["top_terms"]),
        }
        for episode in episodes
    ]

    ordered_terms: list[str] = []
    presence: dict[str, list[bool]] = {}
    for index, episode in enumerate(episodes):
        terms = set(episode["top_terms"])
        for term in sorted(terms):
            if term not in presence:
                presence[term] = [False] * len(episodes)
                ordered_terms.append(term)
            presence[term][index] = True

    details: list[dict[str, Any]] = []
    new_terms: list[str] = []
    disappeared_terms: list[str] = []
    recurring_terms: list[str] = []
    persistent_terms: list[str] = []
    last_index = len(episodes) - 1
    for term in ordered_terms:
        flags = presence[term]
        first_seen = flags.index(True)
        last_seen = last_index - flags[::-1].index(True)
        gaps = any(
            not flags[index]
            for index in range(first_seen, last_seen + 1)
        )
        if first_seen == 0 and last_seen == last_index and not gaps:
            status = "persistent"
            persistent_terms.append(term)
        elif gaps:
            status = "recurring"
            recurring_terms.append(term)
        elif first_seen > 0:
            status = "new"
            new_terms.append(term)
        else:
            status = "disappeared"
            disappeared_terms.append(term)
        details.append(
            {
                "term": term,
                "status": status,
                "first_episode_id": episodes[first_seen]["episode_id"],
                "last_episode_id": episodes[last_seen]["episode_id"],
                "episode_labels": [
                    episodes[index]["label"]
                    for index, present in enumerate(flags)
                    if present
                ],
                "presence": flags,
            }
        )

    return {
        "narrative_cluster_id": narrative_id,
        "method": KEYWORD_EVOLUTION_METHOD,
        "episode_count": len(episodes),
        "episode_terms": episode_terms,
        "new_terms": sorted(new_terms),
        "disappeared_terms": sorted(disappeared_terms),
        "recurring_terms": sorted(recurring_terms),
        "persistent_terms": sorted(persistent_terms),
        "terms": details,
        "explanation": (
            f"Frequent terms were extracted separately from each of the "
            f"{len(episodes)} episodes in this cluster and compared by presence. "
            f"{len(new_terms)} terms first appear after the first episode, "
            f"{len(disappeared_terms)} stop appearing before the last episode, "
            f"{len(recurring_terms)} appear again after an absence, and "
            f"{len(persistent_terms)} appear in every episode. This describes "
            "observable wording only; it does not establish coordination, "
            "misinformation, or cause."
        ),
    }

def _context_comparisons(episodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    comparisons: list[dict[str, Any]] = []
    for previous, current in zip(episodes, episodes[1:]):
        if not previous["representative_posts"] or not current["representative_posts"]:
            continue
        previous_terms = set(previous["top_terms"])
        current_terms = set(current["top_terms"])
        shared_terms = sorted(previous_terms & current_terms)
        union_terms = previous_terms | current_terms
        comparisons.append(
            {
                "comparison_id": f"{previous['episode_id']}~{current['episode_id']}",
                "narrative_cluster_id": previous["narrative_cluster_id"],
                "from_episode_id": previous["episode_id"],
                "to_episode_id": current["episode_id"],
                "from_label": previous["label"],
                "to_label": current["label"],
                "from_post": previous["representative_posts"][0],
                "to_post": current["representative_posts"][0],
                "shared_terms": shared_terms,
                "introduced_terms": sorted(current_terms - previous_terms),
                "dropped_terms": sorted(previous_terms - current_terms),
                "term_overlap_ratio": (
                    round(len(shared_terms) / len(union_terms), 3)
                    if union_terms
                    else 0.0
                ),
                "method": CONTEXT_COMPARISON_METHOD,
                "explanation": (
                    f"Quoted posts from {previous['label']} and {current['label']} "
                    f"share {len(shared_terms)} of {len(union_terms) or 0} frequent "
                    "terms. Quotations are reproduced verbatim from stored posts and "
                    "remain traceable by post ID. Wording differences describe the "
                    "text only and do not establish intent or a causal relationship."
                ),
            }
        )
        if len(comparisons) >= MAX_CONTEXT_COMPARISONS:
            break
    return comparisons

def _narrative_evolution(
    narrative_id: str,
    episodes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    transitions: list[dict[str, Any]] = []
    for previous, current in zip(episodes, episodes[1:]):
        previous_terms = set(previous["top_terms"])
        current_terms = set(current["top_terms"])
        previous_sources = set(previous["source_ids"])
        current_sources = set(current["source_ids"])
        union_terms = previous_terms | current_terms
        shared_terms = sorted(previous_terms & current_terms)
        introduced_terms = sorted(current_terms - previous_terms)
        dropped_terms = sorted(previous_terms - current_terms)
        gap_hours = round(
            (
                datetime.fromisoformat(current["episode_start"])
                - datetime.fromisoformat(previous["episode_end"])
            ).total_seconds()
            / 3600,
            2,
        )
        post_delta = current["post_count"] - previous["post_count"]
        if post_delta > 0:
            volume_direction = "higher"
        elif post_delta < 0:
            volume_direction = "lower"
        else:
            volume_direction = "unchanged"
        shared_sources = sorted(previous_sources & current_sources)
        new_sources = sorted(current_sources - previous_sources)
        transitions.append(
            {
                "transition_id": f"{previous['episode_id']}->{current['episode_id']}",
                "narrative_cluster_id": narrative_id,
                "from_episode_id": previous["episode_id"],
                "to_episode_id": current["episode_id"],
                "from_label": previous["label"],
                "to_label": current["label"],
                "from_episode_end": previous["episode_end"],
                "to_episode_start": current["episode_start"],
                "gap_between_episodes_hours": gap_hours,
                "from_post_count": previous["post_count"],
                "to_post_count": current["post_count"],
                "post_count_delta": post_delta,
                "volume_direction": volume_direction,
                "from_source_count": previous["distinct_source_count"],
                "to_source_count": current["distinct_source_count"],
                "shared_source_count": len(shared_sources),
                "new_source_count": len(new_sources),
                "shared_terms": shared_terms,
                "introduced_terms": introduced_terms,
                "dropped_terms": dropped_terms,
                "term_overlap_ratio": (
                    round(len(shared_terms) / len(union_terms), 3)
                    if union_terms
                    else 0.0
                ),
                "method": EVOLUTION_METHOD,
                "explanation": (
                    f"{current['label']} starts {gap_hours:g} hours after "
                    f"{previous['label']} ends and contains "
                    f"{current['post_count']} posts versus {previous['post_count']} "
                    f"({volume_direction} volume). "
                    f"{len(shared_terms)} of {len(union_terms) or 0} frequent terms are "
                    f"shared, {len(new_sources)} of {current['distinct_source_count']} "
                    "sources are new to this episode. This compares observable "
                    "vocabulary, volume, and source overlap between two separate time "
                    "windows; it does not establish that the later discussion was "
                    "caused by, coordinated with, or a continuation of the earlier one."
                ),
            }
        )
    return transitions

def _temporal_episodes(
    posts: list[Post],
    narrative_id: str,
    temporal_gap_hours: float,
    volume_review: dict[str, Any] | None,
    terms_by_post_id: dict[str, set[str]],
) -> tuple[list[dict[str, Any]], list[str]]:
    ordered_posts = sorted(posts, key=lambda post: _utc_timestamp(post.timestamp))
    gap = timedelta(hours=temporal_gap_hours)
    segments: list[list[Post]] = []
    for post in ordered_posts:
        if (
            not segments
            or _utc_timestamp(post.timestamp)
            - _utc_timestamp(segments[-1][-1].timestamp)
            > gap
        ):
            segments.append([post])
        else:
            segments[-1].append(post)

    spike_start = (
        datetime.fromisoformat(volume_review["interval_start"])
        if volume_review is not None
        else None
    )
    spike_end = (
        datetime.fromisoformat(volume_review["interval_end"])
        if volume_review is not None
        else None
    )
    episodes: list[dict[str, Any]] = []
    unassigned_post_ids: list[str] = []
    for segment in segments:
        if len(segment) < MIN_EPISODE_SIZE:
            unassigned_post_ids.extend(str(post.id) for post in segment)
            continue

        episode_number = len(episodes) + 1
        segment = sorted(segment, key=lambda post: _utc_timestamp(post.timestamp))
        hourly_counts: dict[datetime, int] = defaultdict(int)
        for post in segment:
            hourly_counts[_hour_key(post.timestamp)] += 1
        peak_hour = min(
            hourly_counts,
            key=lambda hour: (-hourly_counts[hour], hour),
        )
        start = _utc_timestamp(segment[0].timestamp)
        end = _utc_timestamp(segment[-1].timestamp)
        sources = {post.source_id for post in segment if post.source_id}
        evidence = [_evidence(post) for post in segment]
        representatives = [
            evidence[index]
            for index in sorted(
                {0, len(evidence) // 2, len(evidence) - 1}
            )
        ][:MAX_EPISODE_REPRESENTATIVES]
        has_volume_spike = bool(
            spike_start is not None
            and spike_end is not None
            and any(
                spike_start
                <= _utc_timestamp(post.timestamp)
                < spike_end
                for post in segment
            )
        )
        duration_seconds = int((end - start).total_seconds())
        episode_label = f"Episode {episode_number}"
        hourly_volume = _hourly_series(segment)
        source_distribution = _source_distribution(segment)
        episodes.append(
            {
                "episode_id": f"{narrative_id}-episode-{episode_number}",
                "narrative_cluster_id": narrative_id,
                "label": episode_label,
                "episode_start": start.isoformat(),
                "episode_end": end.isoformat(),
                "duration": {
                    "seconds": duration_seconds,
                    "hours": round(duration_seconds / 3600, 4),
                },
                "post_count": len(segment),
                "peak_hour": peak_hour.isoformat(),
                "peak_post_count": hourly_counts[peak_hour],
                "distinct_source_count": len(sources),
                "top_terms": _episode_top_terms(segment, terms_by_post_id),
                "source_ids": sorted(sources),
                "source_distribution": source_distribution,
                "hourly_volume": hourly_volume,
                "representative_posts": representatives,
                "evidence_post_ids": [str(post.id) for post in segment],
                "temporal_gap_threshold": temporal_gap_hours,
                "clustering_method": "normalized_token_tfidf_cosine_connected_components",
                "similarity_threshold": SIMILARITY_THRESHOLD,
                "volume_spike_detected": has_volume_spike,
                "evidence_sufficient": len(segment) >= MIN_EPISODE_SIZE,
                "explanation": (
                    f"Lexically similar posts were observed from "
                    f"{start.isoformat()} to {end.isoformat()} UTC across "
                    f"{len(segment)} posts and {len(sources)} distinct sources. "
                    f"{'A detected hourly volume spike overlaps this episode. ' if has_volume_spike else 'No detected hourly volume spike overlaps this episode. '}"
                    "This is a time-bounded evidence group for analyst review, not evidence "
                    "of coordination, misinformation, or intent."
                ),
            }
        )
    return episodes, unassigned_post_ids


def _similar_narratives(
    posts: list[Post],
    temporal_gap_hours: float,
    volume_review: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], str | None]:
    if len(posts) > MAX_SIMILARITY_POSTS:
        return [], (
            f"Similarity analysis was skipped because this method is limited to "
            f"{MAX_SIMILARITY_POSTS} posts; time-volume analysis was still completed."
        )

    documents = [_tokens(post.text) for post in posts]
    document_frequency: dict[str, int] = defaultdict(int)
    for terms in documents:
        for term in terms:
            document_frequency[term] += 1

    document_count = len(posts)
    vectors: list[dict[str, float]] = []
    for terms in documents:
        vector = {
            term: (1 + math.log((1 + document_count) / (1 + document_frequency[term])))
            for term in terms
        }
        norm = math.sqrt(sum(weight * weight for weight in vector.values()))
        if norm:
            vector = {term: weight / norm for term, weight in vector.items()}
        vectors.append(vector)

    inverted_index: dict[str, list[int]] = defaultdict(list)
    for index, vector in enumerate(vectors):
        for term in vector:
            inverted_index[term].append(index)

    similarity_sums: dict[tuple[int, int], float] = defaultdict(float)
    candidate_pairs = 0
    for term, indices in inverted_index.items():
        if len(indices) * (len(indices) - 1) // 2 > MAX_CANDIDATE_PAIRS:
            return [], (
                "Similarity analysis was skipped because too many posts share common terms; "
                "time-volume analysis was still completed."
            )
        for position, left in enumerate(indices):
            left_weight = vectors[left][term]
            for right in indices[position + 1 :]:
                candidate_pairs += 1
                if candidate_pairs > MAX_CANDIDATE_PAIRS:
                    return [], (
                        "Similarity analysis was skipped because the candidate-pair limit "
                        "was reached; time-volume analysis was still completed."
                    )
                similarity_sums[(left, right)] += left_weight * vectors[right][term]

    parents = list(range(document_count))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    for (left, right), similarity in similarity_sums.items():
        if similarity >= SIMILARITY_THRESHOLD:
            left_root = find(left)
            right_root = find(right)
            if left_root != right_root:
                parents[right_root] = left_root

    clusters: dict[int, list[int]] = defaultdict(list)
    for index in range(document_count):
        if vectors[index]:
            clusters[find(index)].append(index)

    grouped = [indices for indices in clusters.values() if len(indices) >= MIN_GROUP_SIZE]
    grouped.sort(
        key=lambda indices: (
            -len(indices),
            min(_utc_timestamp(posts[index].timestamp) for index in indices),
        )
    )

    pair_totals: dict[int, float] = defaultdict(float)
    pair_counts: dict[int, int] = defaultdict(int)
    for (left, right), score in similarity_sums.items():
        if score >= SIMILARITY_THRESHOLD:
            root = find(left)
            if root == find(right):
                pair_totals[root] += score
                pair_counts[root] += 1

    narratives: list[dict[str, Any]] = []
    terms_by_post_id = {
        str(posts[index].id): documents[index] for index in range(document_count)
    }
    for group_number, indices in enumerate(grouped[:MAX_NARRATIVE_GROUPS], start=1):
        ordered_indices = sorted(
            indices, key=lambda index: _utc_timestamp(posts[index].timestamp)
        )
        representative = max(
            ordered_indices,
            key=lambda index: (len(documents[index]), -index),
        )
        root = find(indices[0])
        narrative_id = f"narrative-{group_number}"
        group_posts = [posts[index] for index in ordered_indices]
        episodes, unassigned_post_ids = _temporal_episodes(
            group_posts,
            narrative_id,
            temporal_gap_hours,
            volume_review,
            terms_by_post_id,
        )
        top_terms = [
            term
            for term, _ in sorted(
                Counter(
                    term for index in ordered_indices for term in documents[index]
                ).items(),
                key=lambda item: (-item[1], item[0]),
            )[:4]
        ]
        narratives.append(
            {
                "id": narrative_id,
                "label": f"Narrative cluster {group_number}",
                "top_terms": top_terms,
                "post_count": len(indices),
                "mean_similarity": round(
                    pair_totals[root] / pair_counts[root] if pair_counts[root] else 0,
                    3,
                ),
                "start_time": _evidence(posts[ordered_indices[0]])["timestamp"],
                "end_time": _evidence(posts[ordered_indices[-1]])["timestamp"],
                "representative_text": posts[representative].text,
                "evidence_post_ids": [str(posts[index].id) for index in ordered_indices],
                "episodes": episodes,
                "evolution": _narrative_evolution(narrative_id, episodes),
                "keyword_evolution": _keyword_evolution(narrative_id, episodes),
                "context_comparisons": _context_comparisons(episodes),
                "unassigned_post_ids": unassigned_post_ids,
                "evidence": [
                    _evidence(posts[index])
                    for index in ordered_indices[:MAX_GROUP_EVIDENCE]
                ],
            }
        )
    return narratives, None


def _hour_key(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    timestamp = timestamp.astimezone(timezone.utc)
    return timestamp.replace(minute=0, second=0, microsecond=0)


def _trend_and_spike(
    posts: list[Post],
) -> tuple[
    list[dict[str, Any]],
    dict[str, Any] | None,
    bool,
    str | None,
    dict[str, Any] | None,
]:
    counts: dict[datetime, int] = defaultdict(int)
    posts_by_hour: dict[datetime, list[Post]] = defaultdict(list)
    for post in posts:
        hour = _hour_key(post.timestamp)
        counts[hour] += 1
        posts_by_hour[hour].append(post)

    first_hour = min(counts)
    last_hour = max(counts)
    trend: list[dict[str, Any]] = []
    cursor = first_hour
    while cursor <= last_hour:
        trend.append({"timestamp": cursor.isoformat(), "count": counts.get(cursor, 0)})
        cursor += timedelta(hours=1)

    candidate: tuple[datetime, float, float, float, int, int, float] | None = None
    for index, point in enumerate(trend):
        if index < MIN_BASELINE_HOURS:
            continue
        baseline = [entry["count"] for entry in trend[:index]]
        baseline_total = sum(baseline)
        if baseline_total < MIN_BASELINE_POSTS:
            continue
        mean = baseline_total / len(baseline)
        variance = sum((value - mean) ** 2 for value in baseline) / len(baseline)
        standard_deviation = math.sqrt(variance)
        observed = point["count"]
        threshold = max(5.0, mean + 3 * standard_deviation, mean * 2.5)
        if observed < threshold:
            continue
        score = (observed - mean) / max(standard_deviation, 1.0)
        if candidate is None or score > candidate[1]:
            candidate = (
                datetime.fromisoformat(point["timestamp"]),
                score,
                mean,
                standard_deviation,
                len(baseline),
                baseline_total,
                threshold,
            )

    if candidate is None:
        baseline_sufficient = (
            len(trend) >= MIN_BASELINE_HOURS + 1
            and sum(counts.values()) >= MIN_BASELINE_POSTS
        )
        if not baseline_sufficient:
            return trend, None, False, (
                "A spike alert was not generated because the dataset does not contain "
                "at least 24 prior hourly bins and 20 baseline posts."
            ), None
        return trend, None, True, None, None

    (
        spike_hour,
        score,
        baseline_mean,
        baseline_stddev,
        baseline_hours,
        baseline_post_count,
        required_count,
    ) = candidate
    spike_posts = sorted(posts_by_hour[spike_hour], key=lambda post: post.timestamp)
    observed_count = len(spike_posts)
    severity = "high" if observed_count >= max(10, baseline_mean * 4) else "medium"
    volume_review = {
        "interval_start": spike_hour.isoformat(),
        "interval_end": (spike_hour + timedelta(hours=1)).isoformat(),
        "baseline_hours": baseline_hours,
        "baseline_post_count": baseline_post_count,
        "baseline_mean": round(baseline_mean, 4),
        "baseline_standard_deviation": round(baseline_stddev, 4),
        "required_count": round(required_count, 4),
        "observed_count": observed_count,
        "standard_score": round(score, 4),
        "observed_to_baseline_ratio": round(
            observed_count / baseline_mean if baseline_mean else 0,
            4,
        ),
    }
    alert = {
        "narrative_key": "hourly_volume_spike",
        "severity": severity,
        "baseline_count": max(0, round(baseline_mean)),
        "observed_count": observed_count,
        "explanation": (
            f"{observed_count} posts appeared in this hour versus a prior-hour baseline "
            f"mean of {baseline_mean:.2f} (standard deviation {baseline_stddev:.2f}; "
            f"score {score:.2f}). This is a volume signal for analyst review, not evidence "
            "of coordination or intent."
        ),
        "evidence_json": [
            _evidence(post) for post in spike_posts[:MAX_SPIKE_EVIDENCE]
        ],
    }
    return trend, alert, True, None, volume_review


def analyze_posts(
    posts: list[Post],
    temporal_gap_hours: float = DEFAULT_TEMPORAL_GAP_HOURS,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if not posts:
        raise ValueError("Cannot analyze a dataset with no posts")
    if not math.isfinite(temporal_gap_hours) or temporal_gap_hours <= 0:
        raise ValueError("Temporal gap threshold must be a positive number of hours")

    ordered_posts = sorted(posts, key=lambda post: _utc_timestamp(post.timestamp))
    trend, alert, baseline_sufficient, baseline_warning, volume_review = _trend_and_spike(
        ordered_posts
    )
    narratives, similarity_warning = _similar_narratives(
        ordered_posts,
        temporal_gap_hours,
        volume_review,
    )
    if volume_review is not None:
        related_episodes = [
            episode
            for narrative in narratives
            for episode in narrative["episodes"]
            if episode["volume_spike_detected"]
        ]
        volume_review["related_episode_ids"] = [
            episode["episode_id"] for episode in related_episodes
        ]
        volume_review["related_narrative_ids"] = list(
            dict.fromkeys(
                episode["narrative_cluster_id"] for episode in related_episodes
            )
        )

    if alert is not None and volume_review is not None:
        # The alert is built before narratives exist, so the linkage to the
        # narrative cluster and temporal episode is attached here. These are
        # the first overlapping finding, not a claim that every episode of the
        # cluster is the same event.
        alert["dataset_id"] = ordered_posts[0].dataset_id
        alert["narrative_cluster_id"] = (
            volume_review["related_narrative_ids"][0]
            if volume_review["related_narrative_ids"]
            else None
        )
        alert["episode_id"] = (
            volume_review["related_episode_ids"][0]
            if volume_review["related_episode_ids"]
            else None
        )
        alert["detection_interval_start"] = datetime.fromisoformat(
            volume_review["interval_start"]
        )
        alert["detection_interval_end"] = datetime.fromisoformat(
            volume_review["interval_end"]
        )
        alert["detected_at"] = datetime.fromisoformat(volume_review["interval_start"])
        alert["related_episode_ids"] = list(volume_review["related_episode_ids"])
        alert["related_narrative_ids"] = list(volume_review["related_narrative_ids"])

    start = _evidence(ordered_posts[0])["timestamp"]
    end = _evidence(ordered_posts[-1])["timestamp"]
    episode_count = sum(len(narrative["episodes"]) for narrative in narratives)
    transition_count = sum(len(narrative["evolution"]) for narrative in narratives)
    warnings = [
        warning
        for warning in (similarity_warning, baseline_warning)
        if warning is not None
    ]
    metrics = {
        "summary": {
            "post_count": len(ordered_posts),
            "start_time": start,
            "end_time": end,
            "narrative_group_count": len(narratives),
            "temporal_episode_count": episode_count,
            "narrative_evolution_count": transition_count,
            "temporal_gap_threshold_hours": temporal_gap_hours,
            "alert_count": 1 if alert else 0,
            "baseline_sufficient": baseline_sufficient,
            "similarity_threshold": SIMILARITY_THRESHOLD,
        },
        "trend": trend,
        "narratives": narratives,
        "volume_review": volume_review,
        "warnings": warnings,
        "methodology": (
            "Narrative clusters use normalized-token TF-IDF cosine similarity and connected "
            f"components (similarity threshold {SIMILARITY_THRESHOLD:.2f}). Each cluster is "
            f"segmented into temporal episodes when adjacent posts are more than "
            f"{temporal_gap_hours:g} hours apart; episodes require at least "
            f"{MIN_EPISODE_SIZE} posts, and isolated posts remain unassigned. All times are "
            "UTC. Episode evolution entries compare the observable vocabulary, post "
            "volume, and source overlap of consecutive episodes in the same cluster; they "
            "describe change between separate time windows and do not establish "
            "continuation, coordination, or cause. Volume alerts compare hourly counts "
            "with the preceding hourly "
            "history; an alert is created only with at least 24 baseline hours and 20 "
            "baseline posts. These heuristics support review and are not proof of "
            "coordination, misinformation, or intent."
        ),
    }
    return metrics, alert
