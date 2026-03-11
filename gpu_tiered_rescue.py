# Tiered GPU rescue — progressive step caps so easy ones clear fast
import sys, os, time, csv
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from erdos_straus_gpu import gpu_solve_batch, create_gpu_context

def main():
    with open("unsolved_ns.txt") as f:
        unsolved = [int(line.strip()) for line in f if line.strip()]

    tiers = [
        (5_000_000,   "5M"),
        (10_000_000,  "10M"),
        (25_000_000,  "25M"),
        (50_000_000,  "50M"),
    ]

    print(f"[tiered] Starting with {len(unsolved):,} unsolved values")
    ctx, dev = create_gpu_context()

    fields = ["n", "x", "y", "z", "steps", "solved", "run_id"]
    with open("rescue_results.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for cap, label in tiers:
            if not unsolved:
                print("All solved!")
                break

            print(f"\n[tier {label}] {len(unsolved):,} values at step_cap={cap:,}")
            batch_size = 4096 if cap <= 10_000_000 else 2048 if cap <= 25_000_000 else 1024
            total_batches = (len(unsolved) + batch_size - 1) // batch_size
            tier_solved = 0
            still_unsolved = []
            t0 = time.time()

            for i in range(0, len(unsolved), batch_size):
                batch = unsolved[i:i + batch_size]
                batch_num = i // batch_size + 1

                bt = time.time()
                results = gpu_solve_batch(batch, step_cap=cap, ctx=ctx)
                elapsed = time.time() - bt

                batch_solved = 0
                for r in results:
                    r["run_id"] = f"rescue_{label}"
                    if r["solved"]:
                        batch_solved += 1
                        tier_solved += 1
                    else:
                        still_unsolved.append(r["n"])
                    writer.writerow(r)

                if batch_num % 10 == 0:
                    f.flush()
                    print(f"  batch {batch_num}/{total_batches}: "
                          f"{batch_solved}/{len(batch)} in {elapsed:.1f}s "
                          f"(tier total: {tier_solved:,})")

            tier_time = time.time() - t0
            f.flush()
            print(f"[tier {label}] Solved {tier_solved:,} in {tier_time:.1f}s "
                  f"-- {len(still_unsolved):,} remain")
            unsolved = still_unsolved

    print(f"\nFinal unsolved: {len(unsolved):,}")

if __name__ == "__main__":
    main()
