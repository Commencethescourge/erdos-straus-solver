"""Auto-rescue coordinator — chains CPU chunks and picks up phone leftovers."""
import subprocess
import sys
import time
import os

CHUNKS = [
    ("cpu_chunk6.txt", "run_cpu6.py", "cpu_rescue6_results.csv"),
    ("cpu_chunk7.txt", "run_cpu7.py", "cpu_rescue7_results.csv"),
    ("cpu_chunk8.txt", "run_cpu8.py", "cpu_rescue8_results.csv"),
]

# Phone chunk — CPU will pick this up if phone hasn't finished
PHONE_FALLBACK = ("phone_chunk.txt", "cpu_rescue_phone_results.csv")

WORKERS = 12
STEP_CAP = 10_000_000


def count_lines(path):
    if not os.path.exists(path):
        return 0
    with open(path) as f:
        return sum(1 for _ in f)


def run_chunk(script, cap, workers, chunk_file):
    print(f"\n{'='*60}")
    print(f"[auto] Launching: {script} on {chunk_file}")
    print(f"{'='*60}")
    proc = subprocess.run(
        [sys.executable, script, str(cap), str(workers), chunk_file],
        cwd=os.path.dirname(os.path.abspath(__file__))
    )
    return proc.returncode


def main():
    t0 = time.time()

    for chunk_file, script, results_file in CHUNKS:
        if not os.path.exists(chunk_file):
            print(f"[auto] {chunk_file} not found, skipping")
            continue
        # Skip if results already complete
        if os.path.exists(results_file):
            expected = count_lines(chunk_file)
            done = count_lines(results_file) - 1  # minus header
            if done >= expected:
                print(f"[auto] {results_file} already complete ({done:,}/{expected:,}), skipping")
                continue
            else:
                print(f"[auto] {results_file} partial ({done:,}/{expected:,}), re-running")
        run_chunk(script, STEP_CAP, WORKERS, chunk_file)

    # Check if phone chunk needs CPU rescue
    phone_results = "phone_results.csv"
    phone_chunk = PHONE_FALLBACK[0]
    phone_cpu_out = PHONE_FALLBACK[1]

    if os.path.exists(phone_chunk):
        phone_total = count_lines(phone_chunk)
        phone_done = count_lines(phone_results) - 1 if os.path.exists(phone_results) else 0

        if phone_done < phone_total * 0.9:
            print(f"\n[auto] Phone only solved {phone_done}/{phone_total} — CPU picking up the slack")
            # Create a temp launcher for phone chunk
            import cpu_rescue
            import csv
            import multiprocessing as mp

            with open(phone_chunk) as f:
                unsolved = [int(line.strip()) for line in f if line.strip()]

            total = len(unsolved)
            print(f"[auto-phone] {total:,} values, step_cap={STEP_CAP:,}, workers={WORKERS}")

            fields = ["n", "x", "y", "z", "steps", "solved", "run_id"]
            solved_count = 0
            batch_size = WORKERS * 8

            with open(phone_cpu_out, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                with mp.Pool(WORKERS) as pool:
                    for i in range(0, total, batch_size):
                        batch = unsolved[i:i + batch_size]
                        batch_num = i // batch_size + 1
                        total_batches = (total + batch_size - 1) // batch_size
                        bt = time.time()
                        results = pool.map(cpu_rescue.worker, [(n, STEP_CAP) for n in batch])
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

            print(f"[auto-phone] Solved: {solved_count:,} / {total:,}")
        else:
            print(f"[auto] Phone chunk looks complete ({phone_done}/{phone_total}), skipping")

    total_time = time.time() - t0
    print(f"\n[auto] All done in {total_time:.0f}s")


if __name__ == "__main__":
    import multiprocessing as mp
    mp.freeze_support()
    main()
