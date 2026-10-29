import math
import re
from collections import defaultdict
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
MAX_NARRATIVE_GROUPS = 8
MAX_SPIKE_EVIDENCE = 8
MIN_BASELINE_HOURS = 24
MIN_BASELINE_POSTS = 20


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in TOKEN_PATTERN.findall(text.casefold())
        if token not in STOP_WORDS
    }


def _evidence(post: Post) -> dict[str, Any]:
    timestamp = post.timestamp
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return {
        "post_id": str(post.id),
        "timestamp": timestamp.astimezone(timezone.utc).isoformat(),
        "source_id": post.source_id,
        "text": post.text,
    }


def _similar_narratives(posts: list[Post]) -> tuple[list[dict[str, Any]], str | None]:
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
            min(posts[index].timestamp for index in indices),
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
    for group_number, indices in enumerate(grouped[:MAX_NARRATIVE_GROUPS], start=1):
        ordered_indices = sorted(indices, key=lambda index: posts[index].timestamp)
        representative = max(
            ordered_indices,
            key=lambda index: (len(documents[index]), -index),
        )
        root = find(indices[0])
        narratives.append(
            {
                "id": f"narrative-{group_number}",
                "label": "Similar text group",
                "post_count": len(indices),
                "mean_similarity": round(
                    pair_totals[root] / pair_counts[root] if pair_counts[root] else 0,
                    3,
                ),
                "start_time": _evidence(posts[ordered_indices[0]])["timestamp"],
                "end_time": _evidence(posts[ordered_indices[-1]])["timestamp"],
                "representative_text": posts[representative].text,
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


def analyze_posts(posts: list[Post]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if not posts:
        raise ValueError("Cannot analyze a dataset with no posts")

    ordered_posts = sorted(posts, key=lambda post: post.timestamp)
    narratives, similarity_warning = _similar_narratives(ordered_posts)
    trend, alert, baseline_sufficient, baseline_warning, volume_review = _trend_and_spike(
        ordered_posts
    )

    start = _evidence(ordered_posts[0])["timestamp"]
    end = _evidence(ordered_posts[-1])["timestamp"]
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
            "alert_count": 1 if alert else 0,
            "baseline_sufficient": baseline_sufficient,
            "similarity_threshold": SIMILARITY_THRESHOLD,
        },
        "trend": trend,
        "narratives": narratives,
        "volume_review": volume_review,
        "warnings": warnings,
        "methodology": (
            "Narrative groups use normalized-token TF-IDF cosine similarity and connected "
            "components. Volume alerts compare hourly counts with the preceding hourly "
            "history; an alert is created only with at least 24 baseline hours and 20 "
            "baseline posts. These heuristics support review and are not proof of "
            "coordination, misinformation, or intent."
        ),
    }
    return metrics, alert
