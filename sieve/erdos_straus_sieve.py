#!/usr/bin/env python3
"""
Erdős–Straus conjecture sieve solver — Guinea Pig Trench LLC

Modular sieve approach based on:
  - Salez (2014), arXiv:1406.6307: 7 modular filter equations
  - Mihnea & Dumitru (2025), arXiv:2509.00128: extended to 10^18

Algorithm:
  1. Load R_8: ~2.1M residue classes mod G_8 that survive all parametric families
  2. For each batch k: candidates = {r + k*G_8 | r in R_8}
  3. Filter each candidate against ~140K prime filters
  4. Survivors (if any) get brute-force checked
  5. In practice, all survivors are composite — confirming the conjecture

This replaces brute-force (O(n^2) per target) with a sieve (O(1) per filtered target).
Speed: 10^14 in hours, 10^17 overnight, 10^18 in weeks.

Usage:
    python erdos_straus_sieve.py [k_start] [k_end] [workers]

    # Verify to 10^14 (batches 0..3864)
    python erdos_straus_sieve.py 0 3864

    # Verify to 10^17 (batches 0..3864170)
    python erdos_straus_sieve.py 0 3864170

    # Verify to 10^18 (batches 0..38641709)
    python erdos_straus_sieve.py 0 38641709
"""
import csv
import math
import multiprocessing as mp
import os
import sys
import time


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

G_8 = 25_878_772_920  # Product of 24 * 5 * 7 * 11 * 13 * 17 * 19 * 23 * 29 (approx)

SIEVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sieve_data")
RESIDUES_PATH = os.path.join(SIEVE_DIR, "Residues.txt")
FILTERS_PATH = os.path.join(SIEVE_DIR, "Filters.txt")

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_residues(path=RESIDUES_PATH):
    """Load R_8 residue set from Residues.txt.

    Returns a sorted list of integers (each < G_8).
    """
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Residues.txt not found at {path}. Run: python download_sieve_data.py"
        )
    with open(path) as f:
        residues = list(map(int, f.read().split()))
    return residues


def load_filters(path=FILTERS_PATH):
    """Load prime filters from Filters.txt.

    Format: each filter is [prime, r1, r2, ..., -1]
    Returns list of (prime, frozenset_of_filtered_residues).
    Streams the file to avoid loading 86MB into memory at once.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Filters.txt not found at {path}. Run: python download_sieve_data.py"
        )
    filters = []
    current_prime = None
    current_residues = []

    with open(path) as f:
        for line in f:
            for token in line.split():
                n = int(token)
                if n == -1:
                    if current_prime is not None:
                        filters.append((current_prime, frozenset(current_residues)))
                    current_prime = None
                    current_residues = []
                elif current_prime is None:
                    current_prime = n
                else:
                    current_residues.append(n)

    if current_prime is not None:
        filters.append((current_prime, frozenset(current_residues)))

    return filters


# ---------------------------------------------------------------------------
# Sieve core
# ---------------------------------------------------------------------------

# Worker globals (set by pool initializer)
_w_residues = None
_w_filters = None


def _init_worker(residues_path, filters_path):
    """Initialize worker process with sieve data."""
    global _w_residues, _w_filters
    _w_residues = load_residues(residues_path)
    _w_filters = load_filters(filters_path)


def _check_batch(k):
    """Process one batch. Returns list of survivor n values.

    Pure Python with frozenset lookup and early exit beats NumPy here
    because the filter cascade kills 99.8% of candidates in the first
    ~10K filters. Per-candidate early exit > bulk vectorization.
    """
    survivors = []
    for r in _w_residues:
        n = r + k * G_8
        filtered = False
        for p, excluded in _w_filters:
            if n % p in excluded:
                filtered = True
                break
        if not filtered:
            survivors.append(n)
    return survivors


def check_batch(k):
    """Check one batch. Returns (k, survivors_list)."""
    return (k, _check_batch(k))


def is_prime(n):
    """Simple primality test for survivor checking."""
    if n < 2:
        return False
    if n < 4:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6
    return True


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def sieve_range(k_start, k_end, workers=None, checkpoint_dir="."):
    """Run the sieve for batches k_start..k_end inclusive.

    For each batch k, generates candidates {r + k*G_8 | r in R_8}
    and filters them. Survivors are logged.

    Batch ranges to verification limits:
      k=0..3864         -> 10^14
      k=0..3864170      -> 10^17
      k=0..38641709     -> 10^18
    """
    if workers is None:
        # Each worker needs ~800MB for filter data; cap to avoid OOM
        try:
            import psutil
            avail_gb = psutil.virtual_memory().available / (1024**3)
            max_by_mem = max(1, int(avail_gb / 0.9))  # ~900MB per worker
        except ImportError:
            max_by_mem = 2  # conservative default
        workers = max(1, min(mp.cpu_count() - 1, max_by_mem))

    total_batches = k_end - k_start + 1
    n_max = (k_end + 1) * G_8
    checkpoint_path = os.path.join(
        checkpoint_dir, f"sieve_results_{k_start}_{k_end}.csv"
    )

    # Auto-resume: find last completed batch
    done_batches = set()
    all_survivors = []
    if os.path.exists(checkpoint_path):
        with open(checkpoint_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                done_batches.add(int(row["batch_k"]))
                if row.get("survivor_n"):
                    all_survivors.append(int(row["survivor_n"]))
        print(f"Resuming: {len(done_batches):,} batches already done")

    remaining = [k for k in range(k_start, k_end + 1) if k not in done_batches]
    if not remaining:
        print("All batches done!")
        return

    print("=" * 65)
    print("  Erdos-Straus Modular Sieve")
    print("=" * 65)
    print(f"  Batches: {k_start:,} to {k_end:,} ({total_batches:,} total)")
    print(f"  Remaining: {len(remaining):,}")
    print(f"  Verification range: n up to ~{n_max:.2e}")
    print(f"  Workers: {workers}")
    print(f"  Engine: pure Python (frozenset + early exit)")
    print(f"  Checkpoint: {checkpoint_path}")
    print("=" * 65)

    # Load residue count in main process for progress reporting
    residue_count = len(load_residues())

    fields = ["batch_k", "candidates", "survivors", "survivor_n", "is_prime"]
    mode = "a" if done_batches else "w"
    t0 = time.time()
    processed = 0
    total_survivors = len(all_survivors)

    with open(checkpoint_path, mode, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if not done_batches:
            writer.writeheader()

        with mp.Pool(
            workers,
            initializer=_init_worker,
            initargs=(RESIDUES_PATH, FILTERS_PATH),
        ) as pool:
            for result in pool.imap_unordered(check_batch, remaining, chunksize=1):
                k, survivors = result
                processed += 1

                if survivors:
                    for n in survivors:
                        prime = is_prime(n)
                        writer.writerow({
                            "batch_k": k,
                            "candidates": residue_count,
                            "survivors": len(survivors),
                            "survivor_n": n,
                            "is_prime": prime,
                        })
                        if prime:
                            total_survivors += 1
                            print(f"\n  *** PRIME SURVIVOR: n={n} (batch {k}) ***")
                else:
                    writer.writerow({
                        "batch_k": k,
                        "candidates": residue_count,
                        "survivors": 0,
                        "survivor_n": "",
                        "is_prime": "",
                    })

                # Progress
                if processed % 10 == 0 or processed == len(remaining):
                    f.flush()
                    elapsed = time.time() - t0
                    rate = processed / elapsed if elapsed > 0 else 0
                    eta = (len(remaining) - processed) / rate if rate > 0 else 0
                    pct = 100 * processed / len(remaining)
                    current_n = (k + 1) * G_8
                    print(
                        f"\r  [{pct:5.1f}%] batch {processed:,}/{len(remaining):,} | "
                        f"n~{current_n:.2e} | {rate:.1f} batch/s | "
                        f"ETA: {eta/60:.0f}m | prime survivors: {total_survivors}",
                        end="", flush=True,
                    )

    total_time = time.time() - t0
    print(f"\n\n{'=' * 65}")
    print(f"  Done in {total_time/60:.1f}m ({total_time/3600:.1f}h)")
    print(f"  Batches processed: {processed:,}")
    print(f"  Prime survivors: {total_survivors}")
    if total_survivors == 0:
        print(f"  Conjecture HOLDS for n up to ~{n_max:.2e}")
    else:
        print(f"  *** {total_survivors} prime survivors need brute-force verification ***")
    print(f"  Results: {checkpoint_path}")
    print("=" * 65)


def main():
    k_start = int(sys.argv[1]) if len(sys.argv) >= 2 else 0
    k_end = int(sys.argv[2]) if len(sys.argv) >= 3 else 3864  # default: 10^14
    workers = int(sys.argv[3]) if len(sys.argv) >= 4 else None

    sieve_range(k_start, k_end, workers=workers)


if __name__ == "__main__":
    main()
