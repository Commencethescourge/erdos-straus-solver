#!/usr/bin/env python3
"""
Erdos-Straus Modular Sieve — Lightning.ai Edition
===================================================
Guinea Pig Trench LLC | github.com/Commencethescourge/erdos-straus-solver

Modular sieve verification using Salez (2014) + Mihnea & Dumitru (2025).
Designed for Lightning.ai Studios free tier (4 CPU, 16 GB RAM, always-on).

Usage:
    python erdos_straus_sieve_lightning.py [k_start] [k_end] [workers]

    # Lightning's share of 10^14
    python erdos_straus_sieve_lightning.py 2901 3864 4

    # Full 10^14
    python erdos_straus_sieve_lightning.py 0 3864 4
"""
import csv
import math
import multiprocessing as mp
import os
import subprocess
import sys
import time

G_8 = 25_878_772_920

# Lightning persistent storage
LIGHTNING_DIR = "/teamspace/studios/this_studio"
if os.path.isdir(LIGHTNING_DIR):
    OUTPUT_DIR = LIGHTNING_DIR
else:
    OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

SIEVE_DIR = os.path.join(OUTPUT_DIR, "sieve_data")
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
        try:
            subprocess.run(["wget", "-q", "-O", dest, url], check=True)
        except FileNotFoundError:
            subprocess.run(["curl", "-sL", "-o", dest, url], check=True)
        print(f"  {fname}: {os.path.getsize(dest)/1e6:.1f}MB")


def load_residues(path=None):
    path = path or RESIDUES_PATH
    with open(path) as f:
        return list(map(int, f.read().split()))


def load_filters(path=None):
    path = path or FILTERS_PATH
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
    workers = int(sys.argv[3]) if len(sys.argv) >= 4 else 4

    total_batches = k_end - k_start + 1
    n_max = (k_end + 1) * G_8
    checkpoint = os.path.join(OUTPUT_DIR, f"sieve_results_{k_start}_{k_end}.csv")

    print()
    print("=" * 65)
    print("  Erdos-Straus Modular Sieve — Lightning.ai Edition")
    print("  Guinea Pig Trench LLC")
    print("=" * 65)

    # Download data
    print("Checking sieve data...")
    download_data()

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

    print(f"  Batches: {k_start:,} to {k_end:,} ({total_batches:,} total)")
    print(f"  Remaining: {len(remaining):,}")
    print(f"  Range: n up to ~{n_max:.2e}")
    print(f"  Workers: {workers}")
    print(f"  Output: {checkpoint}")
    print("=" * 65)

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

                if processed % 10 == 0 or processed == len(remaining):
                    f.flush()
                    elapsed = time.time() - t0
                    rate = processed / elapsed if elapsed > 0 else 0
                    eta = (len(remaining) - processed) / rate if rate > 0 else 0
                    pct = 100 * processed / len(remaining)
                    print(
                        f"\r  [{pct:5.1f}%] {processed:,}/{len(remaining):,} | "
                        f"{rate:.1f} batch/s | ETA: {eta/60:.0f}m | "
                        f"prime survivors: {prime_survivors}",
                        end="", flush=True,
                    )

    total_time = time.time() - t0
    print(f"\n\n{'=' * 65}")
    print(f"  Done in {total_time/60:.1f}m ({total_time/3600:.1f}h)")
    print(f"  Batches: {processed:,} | Prime survivors: {prime_survivors}")
    if prime_survivors == 0:
        print(f"  Conjecture HOLDS for n up to ~{n_max:.2e}")
    print(f"  Results: {checkpoint}")
    print("=" * 65)


if __name__ == "__main__":
    mp.freeze_support()
    main()
