#!/usr/bin/env python3
"""
Erdos-Straus sieve solver for Termux (Moto G Power: 8 cores, 4GB RAM)

Downloads sieve data (~114MB) and runs batch verification.
Designed for low-RAM: 2 workers max (~1.2GB each = 2.4GB total).

Usage:
    python phone_sieve.py [k_start] [k_end] [workers]

    # Phone's share of 10^14 (edit K_START/K_END as needed)
    python phone_sieve.py 2901 3864 2

    # Full 10^14
    python phone_sieve.py 0 3864 2
"""
import csv
import math
import multiprocessing as mp
import os
import subprocess
import sys
import time

G_8 = 25_878_772_920

SIEVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sieve_data")
RESIDUES_PATH = os.path.join(SIEVE_DIR, "Residues.txt")
FILTERS_PATH = os.path.join(SIEVE_DIR, "Filters.txt")


def download_data():
    """Download sieve data if not present."""
    os.makedirs(SIEVE_DIR, exist_ok=True)
    for fname in ["Residues.txt", "Filters.txt"]:
        dest = os.path.join(SIEVE_DIR, fname)
        if os.path.exists(dest) and os.path.getsize(dest) > 1000:
            print(f"  {fname}: {os.path.getsize(dest)/1e6:.1f}MB (exists)")
            continue
        url = f"https://github.com/esc-paper/erdos-straus/raw/main/section1/resources/{fname}"
        print(f"  Downloading {fname}...")
        # Try wget first (available in Termux), fall back to curl
        try:
            subprocess.run(["wget", "-q", "-O", dest, url], check=True)
        except FileNotFoundError:
            subprocess.run(["curl", "-sL", "-o", dest, url], check=True)
        print(f"  {fname}: {os.path.getsize(dest)/1e6:.1f}MB")


def load_residues(path=RESIDUES_PATH):
    with open(path) as f:
        return list(map(int, f.read().split()))


def load_filters(path=FILTERS_PATH):
    filters = []
    current_prime = None
    current_residues = []
    with open(path) as f:
        for line in f:
            for token in line.split():
                n = int(token)
                if n == -1:
                    if current_prime is not None:
                        filters.append((current_prime, frozenset(current_residues)))
                    current_prime = None
                    current_residues = []
                elif current_prime is None:
                    current_prime = n
                else:
                    current_residues.append(n)
    if current_prime is not None:
        filters.append((current_prime, frozenset(current_residues)))
    return filters


_w_residues = None
_w_filters = None


def _init_worker(res_path, filt_path):
    global _w_residues, _w_filters
    _w_residues = load_residues(res_path)
    _w_filters = load_filters(filt_path)


def _check_batch(k):
    survivors = []
    for r in _w_residues:
        n = r + k * G_8
        for p, excluded in _w_filters:
            if n % p in excluded:
                break
        else:
            survivors.append(n)
    return survivors


def check_batch(k):
    return (k, _check_batch(k))


def is_prime(n):
    if n < 2: return False
    if n < 4: return True
    if n % 2 == 0 or n % 3 == 0: return False
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0: return False
        i += 6
    return True


def main():
    k_start = int(sys.argv[1]) if len(sys.argv) >= 2 else 2901
    k_end = int(sys.argv[2]) if len(sys.argv) >= 3 else 3864
    workers = int(sys.argv[3]) if len(sys.argv) >= 4 else 2  # 2 for 4GB RAM

    print("Erdos-Straus Modular Sieve — Phone Edition")
    print("=" * 50)

    # Download data if needed
    print("Checking sieve data...")
    download_data()

    total_batches = k_end - k_start + 1
    n_max = (k_end + 1) * G_8
    checkpoint = f"sieve_results_{k_start}_{k_end}.csv"

    # Auto-resume
    done_batches = set()
    if os.path.exists(checkpoint):
        with open(checkpoint) as f:
            for row in csv.DictReader(f):
                done_batches.add(int(row["batch_k"]))
        print(f"Resuming: {len(done_batches):,} batches done")

    remaining = [k for k in range(k_start, k_end + 1) if k not in done_batches]
    if not remaining:
        print("All batches done!")
        return

    print(f"Batches: {k_start}-{k_end} ({total_batches:,} total, {len(remaining):,} remaining)")
    print(f"Range: n up to ~{n_max:.2e}")
    print(f"Workers: {workers} (keep low for 4GB RAM)")
    print("=" * 50)

    residue_count = len(load_residues())
    fields = ["batch_k", "candidates", "survivors", "survivor_n", "is_prime"]
    mode = "a" if done_batches else "w"
    t0 = time.time()
    processed = 0
    prime_survivors = 0

    with open(checkpoint, mode, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if not done_batches:
            writer.writeheader()

        with mp.Pool(workers, initializer=_init_worker,
                     initargs=(RESIDUES_PATH, FILTERS_PATH)) as pool:
            for k, survivors in pool.imap_unordered(check_batch, remaining, chunksize=1):
                processed += 1
                if survivors:
                    for n in survivors:
                        prime = is_prime(n)
                        writer.writerow({"batch_k": k, "candidates": residue_count,
                                         "survivors": len(survivors), "survivor_n": n,
                                         "is_prime": prime})
                        if prime:
                            prime_survivors += 1
                            print(f"\n  *** PRIME SURVIVOR: n={n} (batch {k}) ***")
                else:
                    writer.writerow({"batch_k": k, "candidates": residue_count,
                                     "survivors": 0, "survivor_n": "", "is_prime": ""})

                if processed % 5 == 0 or processed == len(remaining):
                    f.flush()
                    elapsed = time.time() - t0
                    rate = processed / elapsed if elapsed > 0 else 0
                    eta = (len(remaining) - processed) / rate if rate > 0 else 0
                    pct = 100 * processed / len(remaining)
                    print(f"\r  [{pct:5.1f}%] {processed:,}/{len(remaining):,} | "
                          f"{rate:.2f} batch/s | ETA: {eta/60:.0f}m | "
                          f"survivors: {prime_survivors}",
                          end="", flush=True)

    total_time = time.time() - t0
    print(f"\n\n{'=' * 50}")
    print(f"Done in {total_time/60:.1f}m ({total_time/3600:.1f}h)")
    print(f"Batches: {processed:,} | Prime survivors: {prime_survivors}")
    if prime_survivors == 0:
        print(f"Conjecture HOLDS for n up to ~{n_max:.2e}")
    print(f"Results: {checkpoint}")
    print("=" * 50)


if __name__ == "__main__":
    main()
