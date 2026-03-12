#!/usr/bin/env python3
"""
Erdős–Straus Conjecture Solver — Lightning.ai Edition
======================================================
Guinea Pig Trench LLC | github.com/Commencethescourge/erdos-straus-solver

Solves 4/n = 1/x + 1/y + 1/z  (x ≤ y ≤ z, positive integers)
for hard-residue candidates (n mod 24 ∈ {1, 17}).

Designed for Lightning.ai Studios free tier (4 CPU, 16 GB RAM, always-on).
Zero external dependencies — stdlib only.

Usage:
    python erdos_straus_lightning.py [start] [end] [step_cap] [workers]

Defaults:
    start     = 100_000_001
    end       = 110_000_000
    step_cap  = 20_000_000
    workers   = 4
"""

import csv
import math
import multiprocessing
import os
import sys
import time

# ---------------------------------------------------------------------------
# Paths — use Lightning persistent storage when available, else cwd
# ---------------------------------------------------------------------------
LIGHTNING_DIR = "/teamspace/studios/this_studio"
if os.path.isdir(LIGHTNING_DIR):
    OUTPUT_DIR = LIGHTNING_DIR
else:
    OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

RESULTS_CSV = os.path.join(OUTPUT_DIR, "lightning_results.csv")
CSV_FIELDS = ["n", "x", "y", "z", "steps", "solved"]

# ---------------------------------------------------------------------------
# Solver (exact algorithm — do not modify)
# ---------------------------------------------------------------------------

def solve_single(n, step_cap=20_000_000, y_cap_per_x=2_000_000):
    if n <= 1:
        return None
    steps = 0
    x_min = max(1, math.ceil(n / 4))
    x_max = n
    for x in range(x_min, x_max + 1):
        num_r = 4 * x - n
        if num_r <= 0:
            steps += 1
            if steps >= step_cap:
                return None
            continue
        den_r = n * x
        y_min = math.ceil(den_r / num_r)
        y_max = 2 * den_r // num_r
        y_steps = 0
        for y in range(max(x, y_min), y_max + 1):
            steps += 1
            y_steps += 1
            if steps >= step_cap:
                return None
            if y_steps >= y_cap_per_x:
                break
            denom_z = num_r * y - den_r
            if denom_z <= 0:
                continue
            num_z = den_r * y
            if num_z % denom_z == 0:
                z = num_z // denom_z
                if z >= y:
                    return {"n": n, "x": x, "y": y, "z": z, "steps": steps}
    return None

# ---------------------------------------------------------------------------
# Worker wrapper for multiprocessing
# ---------------------------------------------------------------------------

def _worker(args):
    n, step_cap = args
    result = solve_single(n, step_cap=step_cap)
    if result is not None:
        return {**result, "solved": True}
    return {"n": n, "x": 0, "y": 0, "z": 0, "steps": step_cap, "solved": False}

# ---------------------------------------------------------------------------
# Hard-residue target generation
# ---------------------------------------------------------------------------

def generate_targets(start, end):
    """Yield n in [start, end] where n mod 24 ∈ {1, 17}."""
    targets = []
    for n in range(start, end + 1):
        if n % 24 in (1, 17):
            targets.append(n)
    return targets

# ---------------------------------------------------------------------------
# Resume support
# ---------------------------------------------------------------------------

def load_solved(csv_path):
    """Return set of n values already present in results CSV."""
    solved = set()
    if not os.path.isfile(csv_path):
        return solved
    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                solved.add(int(row["n"]))
            except (KeyError, ValueError):
                continue
    return solved

def ensure_csv_header(csv_path):
    """Create CSV with header if it doesn't exist."""
    if not os.path.isfile(csv_path):
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()

# ---------------------------------------------------------------------------
# Progress display
# ---------------------------------------------------------------------------

def format_time(seconds):
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        return f"{seconds / 60:.1f}m"
    return f"{seconds / 3600:.1f}h"

def print_progress(done, total, solved, unsolved, elapsed):
    if done == 0:
        eta_str = "..."
        rate = 0.0
    else:
        rate = done / elapsed
        remaining = (total - done) / rate
        eta_str = format_time(remaining)
    pct = 100.0 * done / total if total > 0 else 0.0
    bar_len = 30
    filled = int(bar_len * done / total) if total > 0 else 0
    bar = "#" * filled + "-" * (bar_len - filled)
    sys.stdout.write(
        f"\r  [{bar}] {pct:5.1f}%  |  {done}/{total}  |  "
        f"solved {solved}  unsolved {unsolved}  |  "
        f"{rate:.1f} n/s  ETA {eta_str}   "
    )
    sys.stdout.flush()

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------

def print_banner(start, end, step_cap, workers, total_targets, skipped):
    print()
    print("=" * 68)
    print("  ERDOS-STRAUS CONJECTURE SOLVER  —  Lightning.ai Edition")
    print("  Guinea Pig Trench LLC")
    print("=" * 68)
    print(f"  Range          : {start:>14,} .. {end:>14,}")
    print(f"  Hard residues  : {total_targets + skipped:>14,}")
    print(f"  Already solved : {skipped:>14,}")
    print(f"  To solve       : {total_targets:>14,}")
    print(f"  Step cap       : {step_cap:>14,}")
    print(f"  Workers        : {workers:>14}")
    print(f"  Output CSV     : {RESULTS_CSV}")
    print("=" * 68)
    print()

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def print_summary(csv_path, wall_time):
    solved_count = 0
    unsolved_count = 0
    largest_z = 0
    total_steps = 0
    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            s = row.get("solved", "True")
            if s in ("True", "1", "true"):
                solved_count += 1
                z_val = int(row.get("z", 0))
                if z_val > largest_z:
                    largest_z = z_val
            else:
                unsolved_count += 1
            total_steps += int(row.get("steps", 0))
    total = solved_count + unsolved_count
    avg_steps = total_steps / total if total > 0 else 0

    print()
    print("=" * 68)
    print("  RUN COMPLETE")
    print("=" * 68)
    print(f"  Wall time      : {format_time(wall_time)}")
    print(f"  Solved         : {solved_count:>14,}")
    print(f"  Unsolved       : {unsolved_count:>14,}")
    print(f"  Largest z      : {largest_z:>14,}")
    print(f"  Avg steps      : {avg_steps:>14,.0f}")
    print(f"  Results CSV    : {csv_path}")
    print("=" * 68)
    print()

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # CLI args
    args = sys.argv[1:]
    start    = int(args[0]) if len(args) > 0 else 100_000_001
    end      = int(args[1]) if len(args) > 1 else 110_000_000
    step_cap = int(args[2]) if len(args) > 2 else 20_000_000
    workers  = int(args[3]) if len(args) > 3 else 4

    # Generate targets and filter already-solved
    all_targets = generate_targets(start, end)
    already_done = load_solved(RESULTS_CSV)
    targets = [n for n in all_targets if n not in already_done]

    ensure_csv_header(RESULTS_CSV)
    print_banner(start, end, step_cap, workers, len(targets), len(all_targets) - len(targets))

    if not targets:
        print("  Nothing to do — all targets already solved.")
        print_summary(RESULTS_CSV, 0)
        return

    total = len(targets)
    done = 0
    solved = 0
    unsolved = 0
    t0 = time.time()

    # Flush interval — write to CSV in batches for efficiency
    BATCH = 200
    batch_buf = []

    def flush_batch(buf):
        with open(RESULTS_CSV, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            for row in buf:
                writer.writerow(row)
        buf.clear()

    work_items = [(n, step_cap) for n in targets]

    with multiprocessing.Pool(processes=workers) as pool:
        for result in pool.imap_unordered(_worker, work_items, chunksize=64):
            done += 1
            if result["solved"]:
                solved += 1
            else:
                unsolved += 1
            batch_buf.append(result)
            if len(batch_buf) >= BATCH:
                flush_batch(batch_buf)
            if done % 50 == 0 or done == total:
                print_progress(done, total, solved, unsolved, time.time() - t0)

    # Flush remaining
    if batch_buf:
        flush_batch(batch_buf)

    wall = time.time() - t0
    print()
    print_summary(RESULTS_CSV, wall)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
