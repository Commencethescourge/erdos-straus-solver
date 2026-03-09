# Erdős-Straus conjecture solver — Guinea Pig Trench LLC
"""
Erdős–Straus conjecture solver.

Two-stage pipeline:
  Stage 1 "hunter"           — n=1..50_000, 500K step cap, mod24∈{1,17} filter
  Stage 2 "leviathan_autopsy" — unsolved from Stage 1, 5M step cap

4/n = 1/x + 1/y + 1/z   for positive integers x ≤ y ≤ z.
"""

import csv
import math
import multiprocessing as mp
import os
import tempfile
import time
import uuid
from dataclasses import dataclass
from fractions import Fraction
from typing import Optional

# ---------------------------------------------------------------------------
# Core solver
# ---------------------------------------------------------------------------


@dataclass
class Solution:
    """A decomposition 4/n = 1/x + 1/y + 1/z with x ≤ y ≤ z."""

    n: int
    x: int
    y: int
    z: int
    steps: int


def solve_single(
    n: int, step_cap: int, y_cap_per_x: int = 1_000_000
) -> tuple[Optional[Solution], int]:
    """Find x ≤ y ≤ z such that 4/n = 1/x + 1/y + 1/z.

    Uses a per-x y-iteration cap to avoid exhausting the global budget on a
    single x value.  Falls back to the global step_cap as an overall limit.

    Returns (Solution | None, steps_used).
    """
    if n <= 0:
        return None, 0
    if n == 1:
        return None, 0

    steps = 0
    x_min = max(1, math.ceil(n / 4))
    x_max = n

    for x in range(x_min, x_max + 1):
        num_r = 4 * x - n
        if num_r <= 0:
            steps += 1
            if steps >= step_cap:
                return None, steps
            continue
        den_r = n * x

        y_min = math.ceil(den_r / num_r)
        y_max = 2 * den_r // num_r

        y_steps = 0
        for y in range(max(x, y_min), y_max + 1):
            steps += 1
            y_steps += 1
            if steps >= step_cap:
                return None, steps
            if y_steps >= y_cap_per_x:
                break

            denom_z = num_r * y - den_r
            if denom_z <= 0:
                continue
            num_z = den_r * y
            if num_z % denom_z == 0:
                z = num_z // denom_z
                if z >= y:
                    return Solution(n=n, x=x, y=y, z=z, steps=steps), steps

    return None, steps


def solve_at_x(n: int, x: int, step_cap: int) -> tuple[Optional[Solution], int]:
    """Try to solve 4/n = 1/x + 1/y + 1/z for a fixed x value."""
    num_r = 4 * x - n
    if num_r <= 0:
        return None, 0
    den_r = n * x

    y_min = math.ceil(den_r / num_r)
    y_max = 2 * den_r // num_r

    steps = 0
    for y in range(max(x, y_min), y_max + 1):
        steps += 1
        if steps >= step_cap:
            return None, steps
        denom_z = num_r * y - den_r
        if denom_z <= 0:
            continue
        num_z = den_r * y
        if num_z % denom_z == 0:
            z = num_z // denom_z
            if z >= y:
                return Solution(n=n, x=x, y=y, z=z, steps=steps), steps

    return None, steps


# ---------------------------------------------------------------------------
# CSV safety — str(z) firewall
# ---------------------------------------------------------------------------


def csv_safe(value: int) -> str:
    """Wrap integers >15 digits in ="" to prevent Excel truncation."""
    s = str(value)
    if len(s) > 15:
        return f'="{s}"'
    return s


# ---------------------------------------------------------------------------
# Worker for multiprocessing
# ---------------------------------------------------------------------------


def _worker(args: tuple) -> dict:
    """Process a single n value. Returns a result dict."""
    n, step_cap, run_id = args
    sol, steps = solve_single(n, step_cap)
    if sol is not None:
        return {
            "n": n,
            "x": csv_safe(sol.x),
            "y": csv_safe(sol.y),
            "z": csv_safe(sol.z),
            "steps": steps,
            "solved": True,
            "run_id": run_id,
        }
    return {
        "n": n,
        "x": "",
        "y": "",
        "z": "",
        "steps": steps,
        "solved": False,
        "run_id": run_id,
    }


# ---------------------------------------------------------------------------
# Checkpoint I/O  (atomic via os.replace)
# ---------------------------------------------------------------------------

CSV_FIELDS = ["n", "x", "y", "z", "steps", "solved", "run_id"]


def load_checkpoint(path: str) -> dict[int, dict]:
    """Load previously computed results keyed by n."""
    results: dict[int, dict] = {}
    if not os.path.exists(path):
        return results
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            n = int(row["n"])
            results[n] = row
    return results


def save_checkpoint(path: str, results: dict[int, dict]) -> None:
    """Atomically write results to CSV via a temp file + os.replace()."""
    dir_name = os.path.dirname(os.path.abspath(path))
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for n in sorted(results.keys()):
                writer.writerow(results[n])
        os.replace(tmp_path, path)
    except BaseException:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Stage runners
# ---------------------------------------------------------------------------

HUNTER_RANGE = range(2, 50_001)
HUNTER_CAP = 500_000
LEVIATHAN_CAP = 5_000_000
CHECKPOINT_INTERVAL = 500  # save every N results


def _needs_compute(n: int, mod24_filter: set[int]) -> bool:
    """Return True if n is in the mod24 residue filter set."""
    return (n % 24) in mod24_filter


def run_hunter(
    checkpoint_path: str = "hunter_checkpoint.csv",
    workers: Optional[int] = None,
) -> dict[int, dict]:
    """Stage 1: hunt for solutions across n=2..50_000.

    Only processes n where n%24 ∈ {1, 17} (the hard residue classes).
    All other residues have known parametric families and are solved trivially.
    """
    run_id = uuid.uuid4().hex[:12]
    existing = load_checkpoint(checkpoint_path)

    # Build work list — skip already-solved and non-target residues
    mod24_targets = {1, 17}
    work = []
    for n in HUNTER_RANGE:
        if not _needs_compute(n, mod24_targets):
            continue
        if n in existing and existing[n].get("solved", "") == "True":
            continue
        work.append((n, HUNTER_CAP, run_id))

    if not work:
        print(f"[hunter] nothing to do — {len(existing)} cached results")
        return existing

    print(f"[hunter] {len(work)} targets (mod24∈{{1,17}}), run_id={run_id}")

    results = dict(existing)
    done = 0
    pool_size = workers or max(1, mp.cpu_count() - 1)

    with mp.Pool(pool_size) as pool:
        for result in pool.imap_unordered(_worker, work, chunksize=32):
            results[result["n"]] = result
            done += 1
            if done % CHECKPOINT_INTERVAL == 0:
                save_checkpoint(checkpoint_path, results)
                print(f"  [hunter] checkpoint {done}/{len(work)}")

    save_checkpoint(checkpoint_path, results)
    solved = sum(1 for r in results.values() if r.get("solved", "") in (True, "True"))
    print(f"[hunter] done — {solved}/{len(results)} solved")
    return results


def run_leviathan_autopsy(
    hunter_results: dict[int, dict],
    checkpoint_path: str = "leviathan_checkpoint.csv",
    workers: Optional[int] = None,
) -> dict[int, dict]:
    """Stage 2: retry unsolved nodes from hunter with a 5M step cap."""
    run_id = uuid.uuid4().hex[:12]
    existing = load_checkpoint(checkpoint_path)

    # Collect unsolved from hunter
    unsolved = []
    for n, row in hunter_results.items():
        if row.get("solved", "") in (True, "True"):
            continue
        if n in existing and existing[n].get("solved", "") == "True":
            continue
        unsolved.append((n, LEVIATHAN_CAP, run_id))

    if not unsolved:
        print("[leviathan] all nodes already solved")
        return existing

    print(f"[leviathan] {len(unsolved)} unsolved nodes, run_id={run_id}")

    results = dict(existing)
    done = 0
    pool_size = workers or max(1, mp.cpu_count() - 1)

    with mp.Pool(pool_size) as pool:
        for result in pool.imap_unordered(_worker, unsolved, chunksize=8):
            results[result["n"]] = result
            done += 1
            if done % 50 == 0:
                save_checkpoint(checkpoint_path, results)
                solved_count = sum(
                    1 for r in results.values() if r.get("solved", "") in (True, "True")
                )
                print(
                    f"  [leviathan] {done}/{len(unsolved)} "
                    f"(solved so far: {solved_count})"
                )

    save_checkpoint(checkpoint_path, results)
    solved = sum(1 for r in results.values() if r.get("solved", "") in (True, "True"))
    print(f"[leviathan] done — {solved}/{len(results)} solved")
    return results


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------


def run_pipeline(
    hunter_ckpt: str = "hunter_checkpoint.csv",
    leviathan_ckpt: str = "leviathan_checkpoint.csv",
    workers: Optional[int] = None,
) -> None:
    """Run the full two-stage Erdős–Straus pipeline."""
    t0 = time.time()
    print("=" * 60)
    print("  Erdős–Straus Solver Pipeline")
    print("=" * 60)

    print("\n--- Stage 1: Hunter ---")
    hunter_results = run_hunter(hunter_ckpt, workers)

    print("\n--- Stage 2: Leviathan Autopsy ---")
    run_leviathan_autopsy(hunter_results, leviathan_ckpt, workers)

    elapsed = time.time() - t0
    print(f"\nPipeline complete in {elapsed:.1f}s")


if __name__ == "__main__":
    mp.freeze_support()
    run_pipeline()
