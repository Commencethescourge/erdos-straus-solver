# Final rescue — crack the last 79 holdouts with 100M step cap
# Tries GPU first (OpenCL), falls back to CPU if no GPU available
import math
import multiprocessing as mp
import os
import sys
import time
import csv


def solve_single(n, step_cap=100_000_000, y_cap_per_x=10_000_000):
    """Solve with much higher caps for stubborn values."""
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


def worker(args):
    n, cap = args
    t0 = time.time()
    result = solve_single(n, step_cap=cap)
    elapsed = time.time() - t0
    if result:
        result["solved"] = True
        result["run_id"] = "final_rescue"
        result["time"] = f"{elapsed:.1f}s"
        return result
    return {
        "n": n, "x": 0, "y": 0, "z": 0,
        "steps": cap, "solved": False,
        "run_id": "final_rescue", "time": f"{elapsed:.1f}s",
    }


def try_gpu(holdouts, step_cap):
    """Try GPU solve first — returns (solved_results, still_unsolved)."""
    try:
        import numpy as np
        import pyopencl as cl
        from erdos_straus_gpu import gpu_solve_batch, create_gpu_context
    except (ImportError, RuntimeError) as e:
        print(f"[final] GPU not available: {e}")
        return [], holdouts

    print(f"[final] GPU phase: {len(holdouts)} values, step_cap={step_cap:,}")
    ctx, dev = create_gpu_context()

    t0 = time.time()
    gpu_results = gpu_solve_batch(holdouts, step_cap=step_cap, ctx=ctx)
    elapsed = time.time() - t0

    solved = []
    unsolved = []
    for r in gpu_results:
        if r["solved"]:
            r["run_id"] = "final_rescue_gpu"
            solved.append(r)
        else:
            unsolved.append(r["n"])

    print(f"[final] GPU solved {len(solved)}/{len(holdouts)} in {elapsed:.1f}s")
    return solved, unsolved


def main():
    chunk_file = "final_holdouts.txt"
    out_path = "final_rescue_results.csv"
    step_cap = 100_000_000  # 100M
    workers = max(1, mp.cpu_count() - 1)

    with open(chunk_file) as f:
        holdouts = [int(line.strip()) for line in f if line.strip()]

    total = len(holdouts)
    print(f"[final] {total} holdouts to crack (step_cap={step_cap:,})")
    t0 = time.time()

    # Phase 1: GPU attempt
    gpu_solved, still_unsolved = try_gpu(holdouts, step_cap)

    # Phase 2: CPU for remaining
    cpu_solved = []
    if still_unsolved:
        print(f"\n[final] CPU phase: {len(still_unsolved)} values, "
              f"step_cap={step_cap:,}, workers={workers}")
        done = 0
        with mp.Pool(workers) as pool:
            for result in pool.imap_unordered(worker,
                    [(n, step_cap) for n in still_unsolved]):
                done += 1
                status = "SOLVED" if result["solved"] else "FAILED"
                print(f"  [{done}/{len(still_unsolved)}] n={result['n']:,} "
                      f"-- {status} ({result['time']})")
                if result["solved"]:
                    cpu_solved.append(result)
                else:
                    cpu_solved.append(result)  # still write failures

    # Write all results
    fields = ["n", "x", "y", "z", "steps", "solved", "run_id"]
    all_results = gpu_solved + cpu_solved
    all_results.sort(key=lambda r: r["n"])

    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for r in all_results:
            writer.writerow(r)

    elapsed = time.time() - t0
    total_solved = sum(1 for r in all_results if r.get("solved"))
    total_failed = sum(1 for r in all_results if not r.get("solved"))

    print(f"\n{'='*60}")
    print(f"[final] Done in {elapsed:.1f}s")
    print(f"[final] Solved: {total_solved}/{total}")
    if total_failed:
        print(f"[final] Still unsolved: {total_failed}")
        for r in all_results:
            if not r.get("solved"):
                print(f"  n={r['n']:,}")
    print(f"{'='*60}")


if __name__ == "__main__":
    mp.freeze_support()
    main()
