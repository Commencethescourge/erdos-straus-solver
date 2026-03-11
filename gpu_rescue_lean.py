# Lean GPU rescue — extract unsolved to flat file, solve on GPU, append results
"""
Memory-efficient rescue for 8GB systems.
Reads checkpoints line-by-line instead of loading everything into dicts.
"""
import csv
import sys
import os
import time
import multiprocessing as mp

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from erdos_straus_gpu import gpu_solve_batch, create_gpu_context
from io_safety import csv_safe


def extract_unsolved():
    """Stream through checkpoint CSVs, collect only unsolved n values."""
    solved_ns = set()

    # Pass 1: collect all solved n from both checkpoints
    for path in ["hunter_gpu_checkpoint.csv", "leviathan_gpu_checkpoint.csv"]:
        if not os.path.exists(path):
            continue
        with open(path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("solved", "") == "True":
                    solved_ns.add(int(row["n"]))

    # Pass 2: collect all n from hunter checkpoint
    all_ns = set()
    with open("hunter_gpu_checkpoint.csv", "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            all_ns.add(int(row["n"]))

    unsolved = sorted(all_ns - solved_ns)
    print(f"[lean-rescue] Total tracked: {len(all_ns):,}")
    print(f"[lean-rescue] Already solved: {len(solved_ns):,}")
    print(f"[lean-rescue] Unsolved: {len(unsolved):,}")
    return unsolved


def rescue(step_cap=50_000_000):
    """GPU rescue with minimal RAM footprint."""
    print("[lean-rescue] Scanning checkpoints (streaming, low RAM)...")
    unsolved = extract_unsolved()

    if not unsolved:
        print("All solved!")
        return

    print(f"[lean-rescue] GPU step_cap: {step_cap:,}")
    ctx, dev = create_gpu_context()

    batch_size = 2048
    total_batches = (len(unsolved) + batch_size - 1) // batch_size
    solved_count = 0
    t0 = time.time()

    # Write results to a separate rescue CSV (append mode)
    rescue_path = "rescue_results.csv"
    fields = ["n", "x", "y", "z", "steps", "solved", "run_id"]
    write_header = not os.path.exists(rescue_path)

    with open(rescue_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if write_header:
            writer.writeheader()

        for i in range(0, len(unsolved), batch_size):
            batch = unsolved[i:i + batch_size]
            batch_num = i // batch_size + 1

            bt = time.time()
            results = gpu_solve_batch(batch, step_cap=step_cap, ctx=ctx)
            bt_elapsed = time.time() - bt

            batch_solved = 0
            for r in results:
                r["run_id"] = "rescue"
                if r["solved"]:
                    batch_solved += 1
                    solved_count += 1
                    writer.writerow(r)

            if batch_num % 5 == 0:
                f.flush()

            print(f"  [rescue] batch {batch_num}/{total_batches}: "
                  f"{batch_solved}/{len(batch)} solved in {bt_elapsed:.1f}s "
                  f"(total rescued: {solved_count:,})")

    elapsed = time.time() - t0
    remaining = len(unsolved) - solved_count
    print(f"\n[lean-rescue] Done in {elapsed:.1f}s")
    print(f"[lean-rescue] Rescued: {solved_count:,}")
    print(f"[lean-rescue] Still unsolved: {remaining:,}")
    print(f"[lean-rescue] Results appended to: {rescue_path}")


if __name__ == "__main__":
    mp.freeze_support()
    cap = 50_000_000
    if len(sys.argv) >= 2:
        cap = int(sys.argv[1])
    rescue(step_cap=cap)
