# Ultra-lean GPU rescue — reads unsolved from flat text file
import sys, os, time, csv
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from erdos_straus_gpu import gpu_solve_batch, create_gpu_context
from io_safety import csv_safe

def main():
    cap = int(sys.argv[1]) if len(sys.argv) >= 2 else 50_000_000

    # Read unsolved n values from flat file (tiny RAM footprint)
    with open("unsolved_ns.txt") as f:
        unsolved = [int(line.strip()) for line in f if line.strip()]

    print(f"[rescue] {len(unsolved):,} unsolved values")
    print(f"[rescue] GPU step_cap: {cap:,}")

    ctx, dev = create_gpu_context()
    batch_size = 2048
    total_batches = (len(unsolved) + batch_size - 1) // batch_size
    solved_count = 0
    t0 = time.time()

    fields = ["n", "x", "y", "z", "steps", "solved", "run_id"]
    with open("rescue_results.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for i in range(0, len(unsolved), batch_size):
            batch = unsolved[i:i + batch_size]
            batch_num = i // batch_size + 1

            bt = time.time()
            results = gpu_solve_batch(batch, step_cap=cap, ctx=ctx)
            elapsed = time.time() - bt

            batch_solved = 0
            for r in results:
                r["run_id"] = "rescue"
                if r["solved"]:
                    batch_solved += 1
                    solved_count += 1
                writer.writerow(r)

            if batch_num % 5 == 0:
                f.flush()

            print(f"  batch {batch_num}/{total_batches}: "
                  f"{batch_solved}/{len(batch)} in {elapsed:.1f}s "
                  f"(rescued: {solved_count:,})")

    total_time = time.time() - t0
    print(f"\nDone in {total_time:.1f}s")
    print(f"Rescued: {solved_count:,} / {len(unsolved):,}")
    print(f"Still unsolved: {len(unsolved) - solved_count:,}")

if __name__ == "__main__":
    main()
