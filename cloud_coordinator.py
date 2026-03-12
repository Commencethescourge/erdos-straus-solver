# cloud_coordinator.py — Split ranges across platforms and merge results
# Guinea Pig Trench LLC
"""
Coordinate distributed solving across multiple free cloud platforms.

Supports two modes:
  1. Sieve mode (default): split batch ranges for the modular sieve solver
  2. Legacy brute-force mode: split n-ranges for the direct solver

Usage:
  # Sieve mode — split batches across fleet
  python cloud_coordinator.py sieve 0 3864          # 10^14
  python cloud_coordinator.py sieve 0 3864170       # 10^17
  python cloud_coordinator.py sieve 0 38641709      # 10^18

  # Legacy brute-force mode
  python cloud_coordinator.py split 100000001 200000000 5

  python cloud_coordinator.py merge
  python cloud_coordinator.py status
"""
import csv
import glob
import math
import os
import sys

G_8 = 25_878_772_920  # Sieve modulus


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


# Sieve fleet: platforms sorted by capability (RAM determines worker count)
SIEVE_FLEET = [
    {"name": "kaggle",    "cores": 4, "ram_gb": 29, "workers": 4, "notebook": "erdos_straus_sieve_kaggle.ipynb"},
    {"name": "colab",     "cores": 2, "ram_gb": 12, "workers": 4, "notebook": "erdos_straus_sieve_colab.ipynb"},
    {"name": "sagemaker", "cores": 4, "ram_gb": 16, "workers": 4, "notebook": "erdos_straus_sieve_sagemaker.ipynb"},
    {"name": "lightning", "cores": 4, "ram_gb": 16, "workers": 4, "notebook": "erdos_straus_lightning.py"},
]


def cmd_sieve(k_start, k_end):
    """Split sieve batches across the cloud fleet."""
    total_batches = k_end - k_start + 1
    n_max = (k_end + 1) * G_8
    num_platforms = len(SIEVE_FLEET)
    chunk_size = math.ceil(total_batches / num_platforms)

    print(f"{'=' * 70}")
    print(f"  Erdos-Straus Modular Sieve — Fleet Distribution")
    print(f"{'=' * 70}")
    print(f"  Total batches: {total_batches:,} (k={k_start}..{k_end})")
    print(f"  Verification range: n up to ~{n_max:.2e}")
    print(f"  Platforms: {num_platforms}")
    print(f"{'=' * 70}")

    assignments = []
    for i, platform in enumerate(SIEVE_FLEET):
        c_start = k_start + i * chunk_size
        c_end = min(k_start + (i + 1) * chunk_size - 1, k_end)
        if c_start > k_end:
            break
        batches = c_end - c_start + 1
        # Estimate: ~21s per batch per worker, workers process in parallel
        est_hours = (batches * 21) / (platform["workers"] * 3600)
        assignments.append((platform, c_start, c_end, batches, est_hours))

    for platform, c_start, c_end, batches, est_hours in assignments:
        print(f"\n  [{platform['name']}] K_START={c_start}, K_END={c_end}")
        print(f"    Batches: {batches:,} | Workers: {platform['workers']}")
        print(f"    RAM: {platform['ram_gb']}GB | Est: {est_hours:.1f}h")
        print(f"    Notebook: {platform['notebook']}")

    print(f"\n{'=' * 70}")
    print(f"  Estimated wall time (all parallel): {max(h for _, _, _, _, h in assignments):.1f}h")
    print(f"  Estimated wall time (sequential):   {sum(h for _, _, _, _, h in assignments):.1f}h")
    print(f"{'=' * 70}")

    print(f"\nQuick setup — edit K_START/K_END in each notebook:")
    for platform, c_start, c_end, _, _ in assignments:
        print(f"  {platform['notebook']}: K_START={c_start}, K_END={c_end}")


def cmd_split(start, end, num_chunks):
    """Generate chunk assignments for each platform (legacy brute-force mode)."""
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
    """Merge all result CSV files (both sieve and brute-force)."""
    # Sieve results
    sieve_patterns = ["sieve_results_*.csv"]
    # Brute-force results
    bf_patterns = [
        "cloud_results_*.csv", "colab_results_*.csv", "erdos_results_*.csv",
        "phone_results_*.csv", "results_*.csv", "kaggle_results_*.csv",
        "lightning_results_*.csv", "sagemaker_results_*.csv",
    ]

    # Merge sieve results
    sieve_files = []
    sieve_batches = set()
    sieve_prime_survivors = []
    for pattern in sieve_patterns:
        for f in glob.glob(pattern):
            sieve_files.append(f)
            with open(f) as csvf:
                reader = csv.DictReader(csvf)
                for row in reader:
                    sieve_batches.add(int(row["batch_k"]))
                    if row.get("is_prime", "").lower() == "true":
                        sieve_prime_survivors.append(row)

    if sieve_files:
        print(f"Sieve results: {len(sieve_files)} files, {len(sieve_batches):,} batches")
        if sieve_batches:
            k_min, k_max = min(sieve_batches), max(sieve_batches)
            n_max = (k_max + 1) * G_8
            print(f"  Batch range: {k_min:,} - {k_max:,}")
            print(f"  Verified up to: ~{n_max:.2e}")
            print(f"  Prime survivors: {len(sieve_prime_survivors)}")
            if not sieve_prime_survivors:
                print(f"  Conjecture HOLDS for sieve range")

    # Merge brute-force results
    all_rows = {}
    bf_files = []
    for pattern in bf_patterns:
        for f in glob.glob(pattern):
            if f == "combined_results.csv":
                continue
            bf_files.append(f)
            with open(f) as csvf:
                reader = csv.DictReader(csvf)
                for row in reader:
                    n = int(row["n"])
                    if n not in all_rows or row.get("solved", "").lower() == "true":
                        all_rows[n] = row

    if bf_files:
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
        print(f"\nBrute-force results: {len(bf_files)} files")
        print(f"  Merged: {len(sorted_rows):,} | Solved: {solved:,} | Unsolved: {unsolved}")
        print(f"  Output: {out}")

    if not sieve_files and not bf_files:
        print("No result files found.")


def cmd_status():
    """Show progress across all result files (sieve + brute-force)."""
    print("=" * 70)
    print("  Fleet Status")
    print("=" * 70)

    # Sieve results
    sieve_total_batches = 0
    for f in sorted(glob.glob("sieve_results_*.csv")):
        batches = set()
        prime_survivors = 0
        with open(f) as csvf:
            reader = csv.DictReader(csvf)
            for row in reader:
                batches.add(int(row["batch_k"]))
                if row.get("is_prime", "").lower() == "true":
                    prime_survivors += 1
        if not batches:
            continue
        k_min, k_max = min(batches), max(batches)
        n_max = (k_max + 1) * G_8
        sieve_total_batches += len(batches)
        print(f"\n  [Sieve] {f}")
        print(f"    Batches: {len(batches):,} (k={k_min}..{k_max})")
        print(f"    Verified up to: ~{n_max:.2e}")
        print(f"    Prime survivors: {prime_survivors}")

    # Brute-force results
    bf_patterns = [
        ("Colab", "colab_results_*.csv"), ("Colab", "erdos_results_*.csv"),
        ("Kaggle", "kaggle_results_*.csv"), ("Lightning", "lightning_results_*.csv"),
        ("SageMaker", "sagemaker_results_*.csv"), ("Phone", "phone_results_*.csv"),
        ("Cloud", "cloud_results_*.csv"), ("Other", "results_*.csv"),
    ]
    total_solved = 0
    total_unsolved = 0
    for platform, pattern in bf_patterns:
        for f in sorted(glob.glob(pattern)):
            if f == "combined_results.csv":
                continue
            solved = unsolved = 0
            n_min, n_max = float("inf"), 0
            with open(f) as csvf:
                reader = csv.DictReader(csvf)
                for row in reader:
                    n = int(row["n"])
                    n_min, n_max = min(n_min, n), max(n_max, n)
                    if row.get("solved", "").lower() == "true":
                        solved += 1
                    else:
                        unsolved += 1
            total_solved += solved
            total_unsolved += unsolved
            if n_min == float("inf"):
                continue
            print(f"\n  [{platform}] {f}")
            print(f"    Range: {n_min:,} - {n_max:,}")
            print(f"    Done: {solved + unsolved:,} | Solved: {solved:,} | Unsolved: {unsolved}")

    print(f"\n{'=' * 70}")
    if sieve_total_batches:
        print(f"  Sieve: {sieve_total_batches:,} batches completed")
    if total_solved + total_unsolved:
        print(f"  Brute-force: {total_solved + total_unsolved:,} | Solved: {total_solved:,} | Unsolved: {total_unsolved}")
    print("=" * 70)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd == "sieve":
        if len(sys.argv) < 4:
            print("Usage: python cloud_coordinator.py sieve K_START K_END")
            sys.exit(1)
        cmd_sieve(int(sys.argv[2]), int(sys.argv[3]))
    elif cmd == "split":
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
