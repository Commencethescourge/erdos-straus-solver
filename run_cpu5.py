import cpu_rescue
import sys

# Override output path to avoid collisions
cpu_rescue_main = cpu_rescue.main

def patched_main():
    import csv, multiprocessing as mp, time
    cap = int(sys.argv[1]) if len(sys.argv) >= 2 else 10_000_000
    workers = int(sys.argv[2]) if len(sys.argv) >= 3 else 12
    chunk_file = sys.argv[3] if len(sys.argv) >= 4 else "cpu_chunk3.txt"

    with open(chunk_file) as f:
        unsolved = [int(line.strip()) for line in f if line.strip()]

    total = len(unsolved)
    print(f"[cpu-rescue4] {total:,} values, step_cap={cap:,}, workers={workers}")

    fields = ["n", "x", "y", "z", "steps", "solved", "run_id"]
    out_path = "cpu_rescue5_results.csv"
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

                results = pool.map(cpu_rescue.worker, [(n, cap) for n in batch])
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
    print(f"\n[cpu-rescue4] Done in {total_time:.1f}s")
    print(f"[cpu-rescue4] Solved: {solved_count:,} / {total:,}")

if __name__ == "__main__":
    import multiprocessing as mp
    mp.freeze_support()
    patched_main()
