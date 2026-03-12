# Micro-batch GPU rescue — tiny batches to avoid GPU stall
import sys, os, time, csv
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from erdos_straus_gpu import gpu_solve_batch, create_gpu_context

def main():
    cap = int(sys.argv[1]) if len(sys.argv) >= 2 else 10_000_000
    batch_size = int(sys.argv[2]) if len(sys.argv) >= 3 else 256

    with open("unsolved_ns.txt") as f:
        unsolved = [int(line.strip()) for line in f if line.strip()]

    print(f"[micro] {len(unsolved):,} unsolved, cap={cap:,}, batch={batch_size}")
    ctx, dev = create_gpu_context()

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

            batch_solved = sum(1 for r in results if r["solved"])
            solved_count += batch_solved
            for r in results:
                r["run_id"] = "micro"
                writer.writerow(r)

            print(f"  {batch_num}/{total_batches}: "
                  f"{batch_solved}/{len(batch)} in {elapsed:.1f}s "
                  f"(total: {solved_count:,})")
            f.flush()

    total_time = time.time() - t0
    print(f"\nDone in {total_time:.1f}s -- rescued {solved_count:,}/{len(unsolved):,}")

if __name__ == "__main__":
    main()
