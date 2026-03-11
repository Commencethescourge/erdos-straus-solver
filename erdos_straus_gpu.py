# Erdős-Straus conjecture solver --GPU-accelerated (OpenCL) --Guinea Pig Trench LLC
"""
GPU-accelerated Erdős–Straus conjecture solver.

Offloads the brute-force search to the AMD Radeon RX 6400 (Navi 24, RDNA 2)
via OpenCL.  Each GPU work-item independently solves one n value.

Falls back to CPU multiprocessing for any n the GPU leaves unsolved
(step cap hit on GPU → retry on CPU with larger budget).

4/n = 1/x + 1/y + 1/z   for positive integers x ≤ y ≤ z.
"""

import math
import multiprocessing as mp
import os
import sys
import time
import uuid
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pyopencl as cl

# Add parent dir to path so io_safety can be found
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from io_safety import csv_safe, load_checkpoint_csv, save_checkpoint_csv

# Import CPU solver as fallback
from erdos_straus import Solution, solve_single, _worker, CSV_FIELDS

# ---------------------------------------------------------------------------
# OpenCL kernel --the core solver running on GPU
# ---------------------------------------------------------------------------

KERNEL_SOURCE = r"""
__kernel void solve_batch(
    __global const int *ns,        // input: array of n values
    __global long *results,        // output: [n, x, y, z, steps] x batch_size (5 longs per n)
    const int batch_size,
    const int step_cap,
    const int y_cap_per_x
) {
    int gid = get_global_id(0);
    if (gid >= batch_size) return;

    long n = (long)ns[gid];
    int base = gid * 5;

    // Default: unsolved
    results[base + 0] = n;
    results[base + 1] = 0;  // x
    results[base + 2] = 0;  // y
    results[base + 3] = 0;  // z
    results[base + 4] = 0;  // steps

    if (n <= 1) return;

    long steps = 0;
    long x_min = (n + 3) / 4;  // ceil(n/4)
    long x_max = n;

    for (long x = x_min; x <= x_max; x++) {
        long num_r = 4 * x - n;
        if (num_r <= 0) {
            steps++;
            if (steps >= step_cap) {
                results[base + 4] = steps;
                return;
            }
            continue;
        }
        long den_r = n * x;

        // y_min = ceil(den_r / num_r)
        long y_min = (den_r + num_r - 1) / num_r;
        long y_max = 2 * den_r / num_r;

        long y_start = (x > y_min) ? x : y_min;
        int y_steps = 0;

        for (long y = y_start; y <= y_max; y++) {
            steps++;
            y_steps++;
            if (steps >= step_cap) {
                results[base + 4] = steps;
                return;
            }
            if (y_steps >= y_cap_per_x) break;

            long denom_z = num_r * y - den_r;
            if (denom_z <= 0) continue;

            long num_z = den_r * y;
            if (num_z % denom_z == 0) {
                long z = num_z / denom_z;
                if (z >= y) {
                    results[base + 0] = n;
                    results[base + 1] = x;
                    results[base + 2] = y;
                    results[base + 3] = z;
                    results[base + 4] = steps;
                    return;
                }
            }
        }
    }

    results[base + 4] = steps;
}
"""

# ---------------------------------------------------------------------------
# GPU context setup
# ---------------------------------------------------------------------------


def create_gpu_context():
    """Create an OpenCL context targeting the AMD GPU."""
    platforms = cl.get_platforms()
    for platform in platforms:
        devices = platform.get_devices(device_type=cl.device_type.GPU)
        if devices:
            ctx = cl.Context(devices=[devices[0]])
            dev = devices[0]
            print(f"[gpu] Using: {dev.name}")
            print(f"[gpu] Compute units: {dev.max_compute_units}, "
                  f"Max workgroup: {dev.max_work_group_size}, "
                  f"VRAM: {dev.global_mem_size // 1024 // 1024} MB")
            return ctx, dev
    raise RuntimeError("No OpenCL GPU device found")


# ---------------------------------------------------------------------------
# GPU batch solver
# ---------------------------------------------------------------------------


def gpu_solve_batch(
    n_values: list[int],
    step_cap: int = 500_000,
    y_cap_per_x: int = 1_000_000,
    ctx: cl.Context = None,
) -> list[dict]:
    """Solve a batch of n values on the GPU.

    Returns list of result dicts compatible with the CPU solver format.
    """
    if ctx is None:
        ctx, dev = create_gpu_context()

    queue = cl.CommandQueue(ctx)
    program = cl.Program(ctx, KERNEL_SOURCE).build()

    batch_size = len(n_values)
    # Input: array of ints
    ns_np = np.array(n_values, dtype=np.int32)
    # Output: 5 longs per n (n, x, y, z, steps)
    results_np = np.zeros(batch_size * 5, dtype=np.int64)

    mf = cl.mem_flags
    ns_buf = cl.Buffer(ctx, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=ns_np)
    results_buf = cl.Buffer(ctx, mf.READ_WRITE | mf.COPY_HOST_PTR, hostbuf=results_np)

    # Launch kernel --one work-item per n value
    # Round up to workgroup size multiple for efficiency
    local_size = 64  # Good default for AMD GCN/RDNA
    global_size = ((batch_size + local_size - 1) // local_size) * local_size

    program.solve_batch(
        queue,
        (global_size,),
        (local_size,),
        ns_buf,
        results_buf,
        np.int32(batch_size),
        np.int32(step_cap),
        np.int32(y_cap_per_x),
    )

    cl.enqueue_copy(queue, results_np, results_buf)
    queue.finish()

    # Parse results
    output = []
    for i in range(batch_size):
        base = i * 5
        n = int(results_np[base + 0])
        x = int(results_np[base + 1])
        y = int(results_np[base + 2])
        z = int(results_np[base + 3])
        steps = int(results_np[base + 4])
        solved = x > 0 and y > 0 and z > 0
        output.append({
            "n": n,
            "x": csv_safe(x) if solved else "",
            "y": csv_safe(y) if solved else "",
            "z": csv_safe(z) if solved else "",
            "steps": steps,
            "solved": solved,
        })
    return output


# ---------------------------------------------------------------------------
# Checkpoint I/O
# ---------------------------------------------------------------------------


def load_checkpoint(path: str) -> dict[int, dict]:
    return load_checkpoint_csv(path, key_field="n")


def save_checkpoint(path: str, results: dict[int, dict]) -> None:
    save_checkpoint_csv(path, results, CSV_FIELDS, sort_key="n")


# ---------------------------------------------------------------------------
# GPU-accelerated pipeline
# ---------------------------------------------------------------------------

GPU_BATCH_SIZE = 4096  # Process this many n values per GPU dispatch
CHECKPOINT_INTERVAL = 2000


def run_hunter_gpu(
    n_range=range(2, 50_001),
    step_cap: int = 500_000,
    checkpoint_path: str = "hunter_gpu_checkpoint.csv",
) -> dict[int, dict]:
    """Stage 1: GPU-accelerated hunter.

    Dispatches batches of hard-residue n values to the GPU.
    Falls back to CPU for any the GPU can't solve within step_cap.
    """
    run_id = uuid.uuid4().hex[:12]
    existing = load_checkpoint(checkpoint_path)

    # Build work list --only hard residues, skip already solved
    mod24_targets = {1, 17}
    work = []
    for n in n_range:
        if (n % 24) not in mod24_targets:
            continue
        if n in existing and existing[n].get("solved", "") in (True, "True"):
            continue
        work.append(n)

    if not work:
        print(f"[gpu-hunter] nothing to do --{len(existing)} cached results")
        return existing

    total = len(work)
    print(f"[gpu-hunter] {total} targets (mod24 in {{1,17}}), run_id={run_id}")
    print(f"[gpu-hunter] GPU batch size: {GPU_BATCH_SIZE}")

    # Set up GPU
    ctx, dev = create_gpu_context()
    results = dict(existing)
    solved_count = 0
    gpu_solved = 0
    gpu_time = 0.0

    # Process in batches
    for batch_start in range(0, total, GPU_BATCH_SIZE):
        batch = work[batch_start:batch_start + GPU_BATCH_SIZE]
        batch_num = batch_start // GPU_BATCH_SIZE + 1
        total_batches = (total + GPU_BATCH_SIZE - 1) // GPU_BATCH_SIZE

        t0 = time.time()
        gpu_results = gpu_solve_batch(batch, step_cap=step_cap, ctx=ctx)
        batch_time = time.time() - t0
        gpu_time += batch_time

        batch_solved = 0
        for r in gpu_results:
            r["run_id"] = run_id
            results[r["n"]] = r
            if r["solved"]:
                batch_solved += 1
                gpu_solved += 1

        solved_count += batch_solved
        print(f"  [gpu-hunter] batch {batch_num}/{total_batches}: "
              f"{batch_solved}/{len(batch)} solved in {batch_time:.2f}s")

        # Checkpoint
        if batch_start % (GPU_BATCH_SIZE * 4) == 0 or batch_start + GPU_BATCH_SIZE >= total:
            save_checkpoint(checkpoint_path, results)

    save_checkpoint(checkpoint_path, results)
    total_solved = sum(1 for r in results.values() if r.get("solved", "") in (True, "True"))
    print(f"[gpu-hunter] GPU phase done --{gpu_solved} solved on GPU in {gpu_time:.2f}s")
    print(f"[gpu-hunter] Total solved: {total_solved}/{len(results)}")
    return results


def run_leviathan_gpu(
    hunter_results: dict[int, dict],
    step_cap: int = 5_000_000,
    checkpoint_path: str = "leviathan_gpu_checkpoint.csv",
) -> dict[int, dict]:
    """Stage 2: GPU-accelerated leviathan autopsy.

    Retries unsolved with higher step cap on GPU, then falls back to CPU
    multiprocessing for anything still stuck.
    """
    run_id = uuid.uuid4().hex[:12]
    existing = load_checkpoint(checkpoint_path)

    unsolved = []
    for n, row in hunter_results.items():
        if row.get("solved", "") in (True, "True"):
            continue
        if n in existing and existing[n].get("solved", "") == "True":
            continue
        unsolved.append(n)

    if not unsolved:
        print("[gpu-leviathan] all nodes already solved")
        return existing

    print(f"[gpu-leviathan] {len(unsolved)} unsolved nodes, run_id={run_id}")

    ctx, dev = create_gpu_context()
    results = dict(existing)

    # Phase A: GPU with higher step cap
    print(f"[gpu-leviathan] Phase A: GPU attack (step_cap={step_cap:,})")
    t0 = time.time()
    gpu_results = gpu_solve_batch(unsolved, step_cap=step_cap, ctx=ctx)
    gpu_time = time.time() - t0

    still_unsolved = []
    gpu_solved = 0
    for r in gpu_results:
        r["run_id"] = run_id
        results[r["n"]] = r
        if r["solved"]:
            gpu_solved += 1
        else:
            still_unsolved.append(r["n"])

    print(f"[gpu-leviathan] GPU solved {gpu_solved}/{len(unsolved)} in {gpu_time:.2f}s")

    # Phase B: CPU fallback for remaining (with even higher cap)
    if still_unsolved:
        cpu_cap = step_cap * 10  # 50M for CPU fallback
        print(f"[gpu-leviathan] Phase B: CPU fallback for {len(still_unsolved)} "
              f"remaining (step_cap={cpu_cap:,})")
        cpu_work = [(n, cpu_cap, run_id) for n in still_unsolved]
        pool_size = max(1, mp.cpu_count() - 1)
        done = 0
        cpu_solved = 0

        with mp.Pool(pool_size) as pool:
            for result in pool.imap_unordered(_worker, cpu_work, chunksize=4):
                results[result["n"]] = result
                done += 1
                if result["solved"]:
                    cpu_solved += 1
                if done % 20 == 0:
                    save_checkpoint(checkpoint_path, results)
                    print(f"  [cpu-fallback] {done}/{len(still_unsolved)} "
                          f"(solved: {cpu_solved})")

        print(f"[gpu-leviathan] CPU fallback solved {cpu_solved}/{len(still_unsolved)}")

    save_checkpoint(checkpoint_path, results)
    total_solved = sum(1 for r in results.values() if r.get("solved", "") in (True, "True"))
    print(f"[gpu-leviathan] done --{total_solved}/{len(results)} solved")
    return results


# ---------------------------------------------------------------------------
# Full GPU-accelerated pipeline
# ---------------------------------------------------------------------------


def run_pipeline(
    n_start: int = 2,
    n_end: int = 50_001,
    hunter_cap: int = 500_000,
    leviathan_cap: int = 5_000_000,
    hunter_ckpt: str = "hunter_gpu_checkpoint.csv",
    leviathan_ckpt: str = "leviathan_gpu_checkpoint.csv",
) -> None:
    """Run the full GPU-accelerated Erdős–Straus pipeline."""
    t0 = time.time()
    print("=" * 60)
    print("  Erdos-Straus GPU-Accelerated Solver")
    print(f"  Range: n={n_start:,}..{n_end - 1:,}")
    print("=" * 60)

    print("\n--- Stage 1: GPU Hunter ---")
    hunter_results = run_hunter_gpu(
        n_range=range(n_start, n_end),
        step_cap=hunter_cap,
        checkpoint_path=hunter_ckpt,
    )

    print("\n--- Stage 2: GPU Leviathan Autopsy ---")
    run_leviathan_gpu(
        hunter_results,
        step_cap=leviathan_cap,
        checkpoint_path=leviathan_ckpt,
    )

    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"  Pipeline complete in {elapsed:.1f}s")
    print(f"{'=' * 60}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mp.freeze_support()

    # Parse optional range from command line
    n_start = 2
    n_end = 50_001
    if len(sys.argv) >= 3:
        n_start = int(sys.argv[1])
        n_end = int(sys.argv[2]) + 1
    elif len(sys.argv) == 2:
        n_end = int(sys.argv[1]) + 1

    run_pipeline(n_start=n_start, n_end=n_end)
