# CPU rescue strand — runs on Ryzen 5600G while GPU handles bulk
import math
import multiprocessing as mp
import os
import sys
import time
import csv


def solve_single(n, step_cap=10_000_000, y_cap_per_x=1_000_000):
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
    result = solve_single(n, step_cap=cap)
    if result:
        result["solved"] = True
        result["run_id"] = "cpu_rescue"
        return result
    return {"n": n, "x": 0, "y": 0, "z": 0, "steps": cap, "solved": False, "run_id": "cpu_rescue"}


def main():
    cap = int(sys.argv[1]) if len(sys.argv) >= 2 else 10_000_000
    workers = int(sys.argv[2]) if len(sys.argv) >= 3 else 10
    chunk_file = sys.argv[3] if len(sys.argv) >= 4 else "cpu_chunk.txt"

    with open(chunk_file) as f:
        unsolved = [int(line.strip()) for line in f if line.strip()]

    total = len(unsolved)
    print(f"[cpu-rescue] {total:,} values, step_cap={cap:,}, workers={workers}")

    fields = ["n", "x", "y", "z", "steps", "solved", "run_id"]
    out_path = "cpu_rescue_results.csv"
    solved_count = 0
    t0 = time.time()

    batch_size = workers * 8

    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        with mp.Pool(workers) as pool:
            for i in range(0, total, batch_size):
                batch = unsolved[i:i + batch_size]
                batch_num = i // batch_size + 1
                total_batches = (total + batch_size - 1) // batch_size
                bt = time.time()

                results = pool.map(worker, [(n, cap) for n in batch])
                elapsed = time.time() - bt

                batch_solved = 0
                for r in results:
                    writer.writerow(r)
                    if r["solved"]:
                        batch_solved += 1
                        solved_count += 1

                if batch_num % 25 == 0 or batch_num == total_batches:
                    f.flush()
                    pct = 100 * (i + len(batch)) / total
                    print(f"  [{pct:5.1f}%] batch {batch_num}/{total_batches}: "
                          f"{batch_solved}/{len(batch)} "
                          f"({elapsed:.1f}s) -- total: {solved_count:,}")

    total_time = time.time() - t0
    print(f"\n[cpu-rescue] Done in {total_time:.1f}s")
    print(f"[cpu-rescue] Solved: {solved_count:,} / {total:,}")


if __name__ == "__main__":
    mp.freeze_support()
    main()
