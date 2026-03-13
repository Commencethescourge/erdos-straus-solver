# Erdos-Straus phone solver v2 — auto-resume, all cores, tmux-friendly
# Designed for Termux on Moto G Power (8 cores, 4GB RAM)
import math
import multiprocessing as mp
import os
import sys
import time
import csv


def solve_single(n, step_cap=20_000_000, y_cap_per_x=2_000_000):
    """Find x <= y <= z such that 4/n = 1/x + 1/y + 1/z."""
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
        return result
    return {"n": n, "x": 0, "y": 0, "z": 0, "steps": cap, "solved": False}


def generate_chunk(start, end):
    """Generate hard-residue targets (n mod 24 in {1,17}) in range."""
    targets = []
    for n in range(start, end + 1):
        if n % 24 in (1, 17):
            targets.append(n)
    return targets


def load_done(results_file):
    """Load already-solved n values from results CSV."""
    done = set()
    if os.path.exists(results_file):
        with open(results_file) as f:
            reader = csv.DictReader(f)
            for row in reader:
                done.add(int(row["n"]))
    return done


def main():
    # Config
    start = int(sys.argv[1]) if len(sys.argv) >= 2 else 100_000_001
    end = int(sys.argv[2]) if len(sys.argv) >= 3 else 110_000_000
    cap = int(sys.argv[3]) if len(sys.argv) >= 4 else 20_000_000
    workers = int(sys.argv[4]) if len(sys.argv) >= 5 else 6  # leave 2 cores free
    results_file = f"phone_results_{start}_{end}.csv"

    print(f"[phone-v2] Range: {start:,} - {end:,}")
    print(f"[phone-v2] Step cap: {cap:,}, Workers: {workers}")
    print(f"[phone-v2] Results: {results_file}")

    # Generate targets
    targets = generate_chunk(start, end)
    print(f"[phone-v2] Total hard-residue targets: {len(targets):,}")

    # Auto-resume: skip already-solved
    done = load_done(results_file)
    if done:
        targets = [n for n in targets if n not in done]
        print(f"[phone-v2] Resuming — {len(done):,} already done, {len(targets):,} remaining")

    if not targets:
        print("[phone-v2] All done!")
        return

    fields = ["n", "x", "y", "z", "steps", "solved"]
    solved_count = len(done)
    unsolved_count = 0
    t0 = time.time()
    batch_size = workers * 4

    # Append mode for resume support
    mode = "a" if done else "w"
    with open(results_file, mode, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if not done:
            writer.writeheader()

        with mp.Pool(workers) as pool:
            for i in range(0, len(targets), batch_size):
                batch = targets[i:i + batch_size]
                results = pool.map(worker, [(n, cap) for n in batch])

                batch_solved = 0
                for r in results:
                    writer.writerow(r)
                    if r["solved"]:
                        batch_solved += 1
                        solved_count += 1
                    else:
                        unsolved_count += 1

                processed = i + len(batch)
                total = len(targets)
                elapsed = time.time() - t0
                rate = processed / elapsed if elapsed > 0 else 0

                # Progress every 100 batches or at boundaries
                if (i // batch_size) % 100 == 0 or processed >= total:
                    f.flush()
                    eta = (total - processed) / rate if rate > 0 else 0
                    print(f"  [{100*processed/total:5.1f}%] {processed:,}/{total:,} | "
                          f"solved: {solved_count:,} | unsolved: {unsolved_count} | "
                          f"{rate:.0f}/s | ETA: {eta/60:.0f}m")

    total_time = time.time() - t0
    print(f"\n[phone-v2] Done in {total_time/60:.1f}m")
    print(f"[phone-v2] Solved: {solved_count:,} | Unsolved: {unsolved_count}")
    print(f"[phone-v2] Results: {results_file}")


if __name__ == "__main__":
    mp.freeze_support()
    main()
