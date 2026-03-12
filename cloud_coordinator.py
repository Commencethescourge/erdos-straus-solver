# cloud_coordinator.py — Split ranges across platforms and merge results
# Guinea Pig Trench LLC
"""
Coordinate distributed solving across multiple free cloud platforms.

Usage:
  python cloud_coordinator.py split 100000001 200000000 5
    → Generates 5 chunk files, one per platform

  python cloud_coordinator.py merge
    → Merges all cloud_results_*.csv and phone_results_*.csv into combined.csv

  python cloud_coordinator.py status
    → Shows progress across all result files
"""
import csv
import glob
import math
import os
import sys


def generate_hard_residues(start, end):
    """Generate n values where n mod 24 in {1, 17}."""
    return [n for n in range(start, end + 1) if n % 24 in (1, 17)]


def split_ranges(start, end, num_chunks):
    """Split a range into num_chunks roughly equal sub-ranges."""
    total = end - start + 1
    chunk_size = math.ceil(total / num_chunks)
    ranges = []
    for i in range(num_chunks):
        c_start = start + i * chunk_size
        c_end = min(start + (i + 1) * chunk_size - 1, end)
        if c_start <= end:
            targets = len(generate_hard_residues(c_start, c_end))
            ranges.append((c_start, c_end, targets))
    return ranges


def cmd_split(start, end, num_chunks):
    """Generate chunk assignments for each platform."""
    platforms = [
        "kaggle",       # 4 cores, 29GB RAM, 12hr, background exec
        "colab",        # 2 cores, 12GB RAM, 12hr
        "lightning",    # 4 cores, 16GB RAM, always-on
        "sagemaker",    # 4 vCPUs, 16GB RAM, 12hr
        "phone",        # 8 cores (slow), 4GB RAM, always-on
    ]

    ranges = split_ranges(start, end, num_chunks)

    print(f"Splitting {start:,} - {end:,} into {len(ranges)} chunks:")
    print(f"Total hard-residue targets: {len(generate_hard_residues(start, end)):,}")
    print("=" * 70)

    for i, (c_start, c_end, targets) in enumerate(ranges):
        platform = platforms[i % len(platforms)]
        print(f"\n  Chunk {i+1}: {c_start:,} - {c_end:,} ({targets:,} targets)")
        print(f"  Platform: {platform}")

        # Write chunk file
        chunk_file = f"chunk_{platform}_{c_start}_{c_end}.txt"
        with open(chunk_file, "w") as f:
            for n in generate_hard_residues(c_start, c_end):
                f.write(f"{n}\n")
        print(f"  File: {chunk_file}")

    print("\n" + "=" * 70)
    print("\nCommands to run on each platform:")
    for i, (c_start, c_end, _) in enumerate(ranges):
        platform = platforms[i % len(platforms)]
        if platform == "phone":
            print(f"\n  [{platform}] ssh phone")
            print(f"    tmux new -s erdos")
            print(f"    python phone_solver_v2.py {c_start} {c_end}")
        elif platform == "lightning":
            print(f"\n  [{platform}] In terminal:")
            print(f"    python erdos_straus_lightning.py {c_start} {c_end}")
        else:
            print(f"\n  [{platform}] Set n_start={c_start:,}, n_end={c_end:,} in notebook")


def cmd_merge():
    """Merge all result CSV files."""
    patterns = [
        "cloud_results_*.csv",
        "colab_results_*.csv",
        "erdos_results_*.csv",
        "phone_results_*.csv",
        "results_*.csv",
        "kaggle_results_*.csv",
        "lightning_results_*.csv",
        "sagemaker_results_*.csv",
    ]

    all_rows = {}
    files_found = []

    for pattern in patterns:
        for f in glob.glob(pattern):
            if f == "combined_results.csv":
                continue
            files_found.append(f)
            with open(f) as csvf:
                reader = csv.DictReader(csvf)
                for row in reader:
                    n = int(row["n"])
                    if n not in all_rows or row.get("solved", "").lower() == "true":
                        all_rows[n] = row

    if not files_found:
        print("No result files found.")
        return

    print(f"Found {len(files_found)} result files:")
    for f in sorted(files_found):
        print(f"  {f}")

    # Write merged
    fields = ["n", "x", "y", "z", "steps", "solved"]
    out = "combined_results.csv"
    sorted_rows = sorted(all_rows.values(), key=lambda r: int(r["n"]))

    with open(out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in sorted_rows:
            writer.writerow({k: row.get(k, "") for k in fields})

    solved = sum(1 for r in sorted_rows if r.get("solved", "").lower() == "true")
    unsolved = len(sorted_rows) - solved

    print(f"\nMerged: {len(sorted_rows):,} total | {solved:,} solved | {unsolved} unsolved")
    print(f"Output: {out}")

    if unsolved > 0:
        print(f"\nUnsolved values:")
        for r in sorted_rows:
            if r.get("solved", "").lower() != "true":
                print(f"  n = {int(r['n']):,}")


def cmd_status():
    """Show progress across all result files."""
    patterns = [
        ("Colab", "colab_results_*.csv"),
        ("Colab", "erdos_results_*.csv"),
        ("Kaggle", "kaggle_results_*.csv"),
        ("Lightning", "lightning_results_*.csv"),
        ("SageMaker", "sagemaker_results_*.csv"),
        ("Phone", "phone_results_*.csv"),
        ("Cloud", "cloud_results_*.csv"),
        ("Other", "results_*.csv"),
    ]

    print("=" * 70)
    print("  Platform Status")
    print("=" * 70)

    total_solved = 0
    total_unsolved = 0

    for platform, pattern in patterns:
        for f in sorted(glob.glob(pattern)):
            if f == "combined_results.csv":
                continue
            solved = 0
            unsolved = 0
            n_min = float("inf")
            n_max = 0
            with open(f) as csvf:
                reader = csv.DictReader(csvf)
                for row in reader:
                    n = int(row["n"])
                    n_min = min(n_min, n)
                    n_max = max(n_max, n)
                    if row.get("solved", "").lower() == "true":
                        solved += 1
                    else:
                        unsolved += 1

            total_solved += solved
            total_unsolved += unsolved
            total = solved + unsolved
            if n_min == float("inf"):
                continue
            print(f"\n  [{platform}] {f}")
            print(f"    Range: {n_min:,} - {n_max:,}")
            print(f"    Done: {total:,} | Solved: {solved:,} | Unsolved: {unsolved}")

    print("\n" + "=" * 70)
    print(f"  TOTAL: {total_solved + total_unsolved:,} | Solved: {total_solved:,} | Unsolved: {total_unsolved}")
    print("=" * 70)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd == "split":
        if len(sys.argv) < 5:
            print("Usage: python cloud_coordinator.py split START END NUM_CHUNKS")
            sys.exit(1)
        cmd_split(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]))
    elif cmd == "merge":
        cmd_merge()
    elif cmd == "status":
        cmd_status()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
