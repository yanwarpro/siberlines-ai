import argparse
import csv
from pathlib import Path

DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "data" / "samples" / "synthetic_posts.csv"
FIELDS = ("timestamp", "text", "source_id", "external_id")
ROWS = (
    {
        "timestamp": "2026-01-01T10:00:00Z",
        "text": "Fictional example post for testing CSV handling.",
        "source_id": "fictional",
        "external_id": "synthetic-001",
    },
    {
        "timestamp": "2026-01-01T10:05:00Z",
        "text": "Synthetic content only; not a real report or threat signal.",
        "source_id": "fictional",
        "external_id": "synthetic-002",
    },
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a clearly labeled fictional CSV fixture.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(ROWS)
    print(f"Wrote {len(ROWS)} synthetic fixture records to {args.output}")


if __name__ == "__main__":
    main()
