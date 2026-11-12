"""Benchmark performance for bulk inserts, fuzzy search, and memory footprint."""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from contact_explorer.models import ContactDraft, EmailAddress, PhoneNumber
from contact_explorer.service import ContactService


def run_benchmark(count: int = 1000) -> None:
    temp_dir = tempfile.TemporaryDirectory()
    db_path = Path(temp_dir.name) / "benchmark.db"

    print("=" * 60)
    print(f" Contact Explorer Performance Benchmark ({count:,} records)")
    print("=" * 60)

    service = ContactService(db_path)

    # 1. Bulk Insertion Benchmark
    print(f"[*] Generating and inserting {count:,} contact records...")
    start_time = time.perf_counter()

    for i in range(count):
        draft = ContactDraft(
            name=f"Benchmark User {i:04d}",
            phones=[PhoneNumber(f"+91 98000 {i:05d}")],
            emails=[EmailAddress(f"user{i}@corp.benchmark.local")],
            company=f"Company {(i % 20):02d}",
            address=f"Suite {i}, Tech Park, Sector {i % 10}",
            note=f"Automated benchmark performance evaluation record #{i}",
            groups=[f"Group_{(i % 5)}"],
            tags=[f"tag_{(i % 10)}", "benchmark"],
            is_favorite=(i % 15 == 0),
        )
        service.save_contact(None, draft)

    insert_elapsed = time.perf_counter() - start_time
    insert_rate = count / insert_elapsed
    print(f"  [✓] Inserted {count:,} records in {insert_elapsed:.2f}s ({insert_rate:.1f} ops/sec)")

    # 2. Database File Size
    db_size_kb = db_path.stat().st_size / 1024
    print(f"  [✓] Database size on disk: {db_size_kb:.1f} KB ({(db_size_kb / count):.2f} KB/contact)")

    # 3. Search Query Benchmarks
    print("\n[*] Executing search performance queries...")
    queries = [
        "Company 05",
        "tag:tag_3",
        "group:Group_2",
        "Benchmark User 0500",
        "User 99",
    ]

    for query in queries:
        q_start = time.perf_counter()
        results = service.search_contacts(query)
        q_elapsed = (time.perf_counter() - q_start) * 1000  # ms
        print(f"  [✓] Search '{query:20s}' -> {len(results):4d} matches in {q_elapsed:.2f} ms")

    # 4. Duplicate Detection Benchmark
    print("\n[*] Running duplicate detection clustering...")
    dup_start = time.perf_counter()
    duplicates = service.duplicate_groups()
    dup_elapsed = (time.perf_counter() - dup_start) * 1000
    print(f"  [✓] Scanned {count:,} contacts for duplicates in {dup_elapsed:.2f} ms (Found {len(duplicates)} duplicate clusters)")

    service.close()
    temp_dir.cleanup()
    print("\n" + "=" * 60)
    print(" Benchmark Completed Successfully.")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Contact Explorer performance")
    parser.add_argument("--count", type=int, default=500, help="Number of contacts to test with")
    args = parser.parse_args()
    run_benchmark(args.count)


if __name__ == "__main__":
    main()
