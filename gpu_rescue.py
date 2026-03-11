# GPU rescue pass — hit the 3M unsolved with higher step caps on GPU
"""
Loads checkpoints from the 100M run, collects unsolved n values,
and hammers them on the GPU with progressively higher step caps.
"""
import sys
import os
import time
import multiprocessing as mp

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from erdos_straus_gpu import (
    gpu_solve_batch, create_gpu_context, load_checkpoint,
    save_checkpoint, GPU_BATCH_SIZE,
)
from erdos_straus import _worker
from io_safety import csv_safe

def collect_unsolved():
    """Merge both checkpoints and find all unsolved n values."""
    h = load_checkpoint("hunter_gpu_checkpoint.csv")
    l = load_checkpoint("leviathan_gpu_checkpoint.csv")
    merged = dict(h)
    merged.update(l)
    unsolved = [
        int(n) for n, r in merged.items()
        if r.get("solved", "") not in (True, "True")
    ]
    unsolved.sort()
    return merged, unsolved


def gpu_rescue(step_cap=50_000_000):
    """Run unsolved through GPU at high step cap in batches."""
    merged, unsolved = collect_unsolved()
    total = len(unsolved)
    if total == 0:
        print("All solved!")
        return merged

    print(f"[rescue] {total:,} unsolved values")
    print(f"[rescue] GPU step_cap: {step_cap:,}")

    ctx, dev = create_gpu_context()
    solved_count = 0
    t0 = time.time()

    batch_size = 2048  # smaller batches for higher step cap = longer per item
    total_batches = (total + batch_size - 1) // batch_size

    for i in range(0, total, batch_size):
        batch = unsolved[i:i + batch_size]
        batch_num = i // batch_size + 1

        bt = time.time()
        results = gpu_solve_batch(batch, step_cap=step_cap, ctx=ctx)
        bt_elapsed = time.time() - bt

        batch_solved = 0
        for r in results:
            r["run_id"] = "rescue"
            merged[r["n"]] = r
            if r["solved"]:
                batch_solved += 1
                solved_count += 1

        print(f"  [rescue] batch {batch_num}/{total_batches}: "
              f"{batch_solved}/{len(batch)} solved in {bt_elapsed:.1f}s "
              f"(total rescued: {solved_count})")

        # Checkpoint every 10 batches
        if batch_num % 10 == 0:
            save_checkpoint("leviathan_gpu_checkpoint.csv", merged)

    elapsed = time.time() - t0
    save_checkpoint("leviathan_gpu_checkpoint.csv", merged)

    remaining = sum(
        1 for r in merged.values()
        if r.get("solved", "") not in (True, "True")
    )
    total_solved = len(merged) - remaining
    print(f"\n[rescue] Done in {elapsed:.1f}s")
    print(f"[rescue] Rescued: {solved_count:,}")
    print(f"[rescue] Total solved: {total_solved:,}/{len(merged):,}")
    print(f"[rescue] Still unsolved: {remaining:,}")
    return merged


if __name__ == "__main__":
    mp.freeze_support()
    cap = 50_000_000
    if len(sys.argv) >= 2:
        cap = int(sys.argv[1])
    gpu_rescue(step_cap=cap)
