from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import Analysis, Dataset, Post
from app.services.analysis_service import _episode_top_terms, analyze_posts
from app.services.csv_service import parse_posts_csv

SAMPLE_DATASET = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "samples"
    / "siberlens_dummy_dataset.csv"
)


def _insert_posts(
    session_factory: sessionmaker[Session],
    rows: list[dict],
) -> str:
    dataset_id = uuid4()
    with session_factory() as session:
        dataset = Dataset(
            id=dataset_id,
            name="Synthetic analysis test",
            source_type="csv_upload",
            row_count=len(rows),
            status="uploaded",
        )
        session.add(dataset)
        session.add_all(
            Post(dataset_id=dataset_id, **row)
            for row in rows
        )
        session.commit()
    return str(dataset_id)


def test_analysis_runs_on_supplied_dataset_and_can_be_reloaded(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, test_session = api_client
    parsed = parse_posts_csv(SAMPLE_DATASET.read_bytes())
    dataset_id = _insert_posts(test_session, parsed.records)

    response = client.post(f"/api/v1/datasets/{dataset_id}/analyses")

    assert response.status_code == 201
    result = response.json()
    assert result["status"] == "completed"
    metrics = result["metrics_json"]
    assert metrics["summary"]["post_count"] == 78
    assert metrics["summary"]["alert_count"] == 1
    assert metrics["summary"]["baseline_sufficient"] is True
    assert metrics["summary"]["temporal_gap_threshold_hours"] == 6
    assert metrics["summary"]["temporal_episode_count"] == sum(
        len(group["episodes"]) for group in metrics["narratives"]
    )
    assert metrics["volume_review"]["interval_start"] == "2026-10-28T14:00:00+00:00"
    assert metrics["volume_review"]["interval_end"] == "2026-10-28T15:00:00+00:00"
    assert metrics["volume_review"]["observed_count"] == 25
    assert metrics["volume_review"]["baseline_mean"] < 1
    assert metrics["volume_review"]["baseline_hours"] >= 24
    assert len(metrics["trend"]) > 24
    assert max(point["count"] for point in metrics["trend"]) == 25
    assert any("Jembatan Kenanga" in group["representative_text"] for group in metrics["narratives"])
    episodes = [
        episode
        for group in metrics["narratives"]
        for episode in group["episodes"]
    ]
    assert episodes
    assert all(episode["post_count"] >= 2 for episode in episodes)
    assert all(episode["narrative_cluster_id"] in {
        group["id"] for group in metrics["narratives"]
    } for episode in episodes)
    assert all(
        episode["temporal_gap_threshold"] == 6
        and episode["similarity_threshold"] == metrics["summary"]["similarity_threshold"]
        and len(episode["evidence_post_ids"]) == episode["post_count"]
        and episode["representative_posts"]
        and all(
            evidence["post_id"] in episode["evidence_post_ids"]
            and evidence["timestamp"].endswith("+00:00")
            for evidence in episode["representative_posts"]
        )
        for episode in episodes
    )
    spike_episodes = [
        episode for episode in episodes if episode["volume_spike_detected"]
    ]
    assert spike_episodes
    assert any(
        episode["episode_start"] >= "2026-10-28T14:00:00+00:00"
        and episode["episode_end"] < "2026-10-28T15:00:00+00:00"
        and episode["peak_hour"] == "2026-10-28T14:00:00+00:00"
        for episode in spike_episodes
    )
    with test_session() as session:
        stored_posts = session.scalars(
            select(Post).where(Post.dataset_id == UUID(dataset_id))
        ).all()
    bridge_burst_ids = {
        str(post.id)
        for post in stored_posts
        if (
            post.timestamp.replace(tzinfo=timezone.utc)
            if post.timestamp.tzinfo is None
            else post.timestamp.astimezone(timezone.utc)
        ).strftime("%Y-%m-%dT%H")
        == "2026-10-28T14"
        and "Jembatan Kenanga" in post.text
    }
    episode_burst_ids = {
        post_id
        for episode in episodes
        for post_id in episode["evidence_post_ids"]
        if post_id in bridge_burst_ids
    }
    assert len(bridge_burst_ids) == 24
    assert episode_burst_ids == bridge_burst_ids
    assert metrics["volume_review"]["related_episode_ids"] == [
        episode["episode_id"] for episode in spike_episodes
    ]
    assert result["alerts"][0]["observed_count"] == 25
    alert_evidence_ids = {
        evidence["post_id"] for evidence in result["alerts"][0]["evidence_json"]
    }
    assert any(
        alert_evidence_ids.intersection(
            evidence["post_id"] for evidence in group["evidence"]
        )
        for group in metrics["narratives"]
    )
    assert "expected_topic" not in str(metrics)
    assert "dataset_label" not in str(metrics)

    analysis_id = result["id"]
    reloaded = client.get(f"/api/v1/analyses/{analysis_id}")
    history = client.get(f"/api/v1/datasets/{dataset_id}/analyses")
    assert reloaded.status_code == 200
    assert reloaded.json() == result
    assert history.status_code == 200
    assert [analysis["id"] for analysis in history.json()] == [analysis_id]

    with test_session() as session:
        saved = session.get(Analysis, UUID(analysis_id))
        assert saved is not None
        assert saved.metrics_json["summary"]["post_count"] == 78
        assert saved.config_json["temporal_gap_hours"] == 6


def test_temporal_gap_threshold_changes_episode_segmentation() -> None:
    parsed = parse_posts_csv(SAMPLE_DATASET.read_bytes())
    dataset_id = uuid4()
    posts = [
        Post(id=uuid4(), dataset_id=dataset_id, **row)
        for row in parsed.records
    ]

    six_hour_metrics, _ = analyze_posts(posts, temporal_gap_hours=6)
    two_hour_metrics, _ = analyze_posts(posts, temporal_gap_hours=2)
    six_hour_count = six_hour_metrics["summary"]["temporal_episode_count"]
    two_hour_count = two_hour_metrics["summary"]["temporal_episode_count"]

    two_hour_unassigned = sum(
        len(group["unassigned_post_ids"])
        for group in two_hour_metrics["narratives"]
    )
    six_hour_unassigned = sum(
        len(group["unassigned_post_ids"])
        for group in six_hour_metrics["narratives"]
    )
    assert two_hour_count != six_hour_count
    assert two_hour_unassigned > six_hour_unassigned
    assert six_hour_metrics["summary"]["temporal_gap_threshold_hours"] == 6
    assert two_hour_metrics["summary"]["temporal_gap_threshold_hours"] == 2
    assert all(
        len(group["unassigned_post_ids"])
        + sum(episode["post_count"] for episode in group["episodes"])
        == group["post_count"]
        for group in six_hour_metrics["narratives"]
    )


def test_larger_temporal_gap_merges_connected_segments() -> None:
    dataset_id = uuid4()
    timestamps = (
        "2026-10-28T00:00:00+00:00",
        "2026-10-28T01:00:00+00:00",
        "2026-10-28T12:00:00+00:00",
        "2026-10-28T13:00:00+00:00",
    )
    posts = [
        Post(
            id=uuid4(),
            dataset_id=dataset_id,
            external_id=f"post-{index}",
            timestamp=datetime.fromisoformat(timestamp).astimezone(timezone.utc),
            source_id=f"source-{index}",
            text="A repeated synthetic bridge update for temporal segmentation.",
            content_hash=f"hash-{index}",
        )
        for index, timestamp in enumerate(timestamps)
    ]

    six_hour_metrics, _ = analyze_posts(posts, temporal_gap_hours=6)
    twelve_hour_metrics, _ = analyze_posts(posts, temporal_gap_hours=12)
    six_hour_episodes = six_hour_metrics["narratives"][0]["episodes"]
    twelve_hour_episodes = twelve_hour_metrics["narratives"][0]["episodes"]

    assert [episode["post_count"] for episode in six_hour_episodes] == [2, 2]
    assert [episode["post_count"] for episode in twelve_hour_episodes] == [4]


def test_analysis_endpoint_persists_configured_temporal_gap(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, test_session = api_client
    parsed = parse_posts_csv(
        b"external_id,timestamp,source_id,text\n"
        b"one,2026-10-28T00:00:00Z,source-a,Repeated bridge update for review\n"
        b"two,2026-10-28T01:00:00Z,source-b,Repeated bridge update for review\n"
        b"three,2026-10-28T12:00:00Z,source-c,Repeated bridge update for review\n"
        b"four,2026-10-28T13:00:00Z,source-d,Repeated bridge update for review\n"
    )
    dataset_id = _insert_posts(test_session, parsed.records)

    response = client.post(
        f"/api/v1/datasets/{dataset_id}/analyses?temporal_gap_hours=12"
    )

    assert response.status_code == 201
    result = response.json()
    assert result["config_json"]["temporal_gap_hours"] == 12
    assert result["metrics_json"]["summary"]["temporal_gap_threshold_hours"] == 12
    assert result["metrics_json"]["summary"]["temporal_episode_count"] == 1


def test_analysis_endpoint_rejects_invalid_temporal_gap(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_client

    response = client.post(
        f"/api/v1/datasets/{uuid4()}/analyses?temporal_gap_hours=0"
    )

    assert response.status_code == 422


def test_short_dataset_does_not_create_spike_alert(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, test_session = api_client
    parsed = parse_posts_csv(
        b"external_id,timestamp,source_id,text\n"
        b"one,2026-10-28T10:00:00Z,simulated,First sample report\n"
        b"two,2026-10-28T10:05:00Z,simulated,Second sample report\n"
        b"three,2026-10-28T10:10:00Z,simulated,Third sample report\n"
    )
    dataset_id = _insert_posts(test_session, parsed.records)

    response = client.post(f"/api/v1/datasets/{dataset_id}/analyses")

    assert response.status_code == 201
    result = response.json()
    assert result["alerts"] == []
    assert result["metrics_json"]["summary"]["alert_count"] == 0
    assert result["metrics_json"]["summary"]["baseline_sufficient"] is False
    assert result["metrics_json"]["volume_review"] is None
    assert any("baseline" in warning for warning in result["metrics_json"]["warnings"])


def test_analysis_rejects_missing_dataset(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_client

    response = client.post(f"/api/v1/datasets/{uuid4()}/analyses")

    assert response.status_code == 404
    assert response.json() == {"detail": "Dataset not found"}


def test_analysis_rejects_dataset_without_posts(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, test_session = api_client
    with test_session() as session:
        dataset = Dataset(name="Empty dataset", row_count=0)
        session.add(dataset)
        session.commit()
        dataset_id = dataset.id

    response = client.post(f"/api/v1/datasets/{dataset_id}/analyses")

    assert response.status_code == 422
    assert response.json() == {"detail": "Cannot analyze a dataset with no posts"}


def test_list_analysis_returns_404_for_missing_dataset(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_client

    response = client.get(f"/api/v1/datasets/{uuid4()}/analyses")

    assert response.status_code == 404

def test_narrative_evolution_compares_consecutive_episodes() -> None:
    parsed = parse_posts_csv(SAMPLE_DATASET.read_bytes())
    posts = [
        Post(id=uuid4(), dataset_id=uuid4(), **row)
        for row in parsed.records
    ]

    metrics, _ = analyze_posts(posts, temporal_gap_hours=6)
    narratives = metrics["narratives"]
    transitions = [
        transition
        for narrative in narratives
        for transition in narrative["evolution"]
    ]

    assert transitions
    assert metrics["summary"]["narrative_evolution_count"] == len(transitions)
    assert all(
        len(narrative["evolution"]) == max(len(narrative["episodes"]) - 1, 0)
        for narrative in narratives
    )
    for narrative in narratives:
        episode_ids = [episode["episode_id"] for episode in narrative["episodes"]]
        assert [
            (transition["from_episode_id"], transition["to_episode_id"])
            for transition in narrative["evolution"]
        ] == list(zip(episode_ids, episode_ids[1:]))

    bridge = next(
        narrative
        for narrative in narratives
        if any("Jembatan Kenanga" in post["text"] for post in narrative["evidence"])
    )
    assert len(bridge["episodes"]) >= 2
    transition = bridge["evolution"][0]
    assert transition["to_post_count"] > transition["from_post_count"]
    assert transition["volume_direction"] == "higher"
    assert transition["post_count_delta"] == (
        transition["to_post_count"] - transition["from_post_count"]
    )
    assert transition["gap_between_episodes_hours"] == round(
        (
            datetime.fromisoformat(bridge["episodes"][1]["episode_start"])
            - datetime.fromisoformat(bridge["episodes"][0]["episode_end"])
        ).total_seconds()
        / 3600,
        2,
    )
    assert transition["from_episode_end"] <= transition["to_episode_start"]
    assert transition["method"] == "episode_term_volume_source_delta"
    assert set(transition["shared_terms"]).isdisjoint(
        set(transition["introduced_terms"])
    )
    assert set(transition["shared_terms"]).isdisjoint(
        set(transition["dropped_terms"])
    )
    assert "does not establish" in transition["explanation"]

def test_narrative_evolution_requires_multiple_episodes() -> None:
    dataset_id = uuid4()
    posts = [
        Post(
            id=uuid4(),
            dataset_id=dataset_id,
            external_id=f"post-{index}",
            timestamp=datetime(2026, 10, 28, index, 0, tzinfo=timezone.utc),
            source_id=f"source-{index}",
            text="Repeated synthetic bridge update for evolution testing.",
            content_hash=f"hash-{index}",
        )
        for index in range(3)
    ]

    metrics, _ = analyze_posts(posts, temporal_gap_hours=6)
    narrative = metrics["narratives"][0]

    assert len(narrative["episodes"]) == 1
    assert narrative["evolution"] == []
    assert metrics["summary"]["narrative_evolution_count"] == 0

def test_episode_top_terms_break_ties_alphabetically() -> None:
    dataset_id = uuid4()
    posts = [
        Post(
            id=uuid4(),
            dataset_id=dataset_id,
            external_id=f"post-{index}",
            timestamp=datetime(2026, 10, 28, index, 0, tzinfo=timezone.utc),
            source_id=f"source-{index}",
            text="Repeated synthetic bridge update for evolution testing.",
            content_hash=f"hash-{index}",
        )
        for index in range(3)
    ]
    terms_by_post_id = {
        str(posts[0].id): {"zebra", "alpha", "mike", "bravo", "yankee", "charlie"},
        str(posts[1].id): {"zebra", "alpha", "mike", "bravo", "yankee", "charlie"},
        str(posts[2].id): {"zebra", "alpha", "mike", "bravo", "yankee", "charlie"},
    }

    ranked = _episode_top_terms(posts, terms_by_post_id)

    assert ranked == ["alpha", "bravo", "charlie", "mike", "yankee"]

def test_saved_analysis_exposes_evolution_metadata(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, test_session = api_client
    parsed = parse_posts_csv(SAMPLE_DATASET.read_bytes())
    dataset_id = _insert_posts(test_session, parsed.records)

    response = client.post(f"/api/v1/datasets/{dataset_id}/analyses")

    assert response.status_code == 201
    result = response.json()
    assert result["metrics_json"]["summary"]["narrative_evolution_count"] > 0
    assert any(
        narrative["evolution"]
        for narrative in result["metrics_json"]["narratives"]
    )

    reloaded = client.get(f"/api/v1/analyses/{result['id']}")

    assert reloaded.status_code == 200
    assert reloaded.json()["metrics_json"]["narratives"] == (
        result["metrics_json"]["narratives"]
    )
