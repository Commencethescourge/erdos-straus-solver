"""Profile the ultra-hard survivors that resist all rescue strands.
Run after merging all results to identify truly unsolved values.

Usage: python survivor_profile.py [unsolved_ns.txt] [results_dir]
"""
import csv
import os
import sys
import math
from collections import Counter


def load_solved_ns(results_dir="."):
    """Load all solved n values from every rescue CSV."""
    solved = set()
    csv_files = [f for f in os.listdir(results_dir)
                 if f.endswith("_results.csv") or f == "rescue_results.csv"]

    for fname in csv_files:
        path = os.path.join(results_dir, fname)
        print(f"  Loading {fname}...", end=" ")
        count = 0
        with open(path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Check if solved (different CSVs use different formats)
                is_solved = False
                if "solved" in row:
                    is_solved = row["solved"] in ("True", "1", "true")
                elif "x" in row:
                    is_solved = int(row.get("x", 0) or 0) > 0
                if is_solved:
                    solved.add(int(row["n"]))
                    count += 1
        print(f"{count:,} solved")

    return solved


def smallest_prime_factor(n):
    if n <= 1:
        return n
    if n % 2 == 0:
        return 2
    for i in range(3, int(math.isqrt(n)) + 1, 2):
        if n % i == 0:
            return i
    return n


def prime_factors(n):
    factors = []
    d = 2
    while d * d <= n:
        while n % d == 0:
            factors.append(d)
            n //= d
        d += 1
    if n > 1:
        factors.append(n)
    return factors


def is_prime(n):
    if n < 2:
        return False
    if n < 4:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6
    return True


def profile_survivors(survivors):
    """Analyze structural properties of survivor n values."""
    if not survivors:
        print("\nNo survivors! Every value was solved.")
        return

    survivors = sorted(survivors)
    print(f"\n{'='*60}")
    print(f"SURVIVOR PROFILE: {len(survivors)} values")
    print(f"{'='*60}")

    # Basic stats
    print(f"\nRange: {survivors[0]:,} to {survivors[-1]:,}")
    print(f"Mean:  {sum(survivors)/len(survivors):,.1f}")
    print(f"Median: {survivors[len(survivors)//2]:,}")

    # Mod 24 distribution
    print(f"\n--- Mod 24 Distribution ---")
    mod24 = Counter(n % 24 for n in survivors)
    for k in sorted(mod24.keys()):
        pct = 100 * mod24[k] / len(survivors)
        bar = "#" * int(pct)
        print(f"  mod24≡{k:2d}: {mod24[k]:6,} ({pct:5.1f}%) {bar}")

    # Mod 24 ∈ {1, 17} breakdown
    hard_residues = sum(1 for n in survivors if n % 24 in (1, 17))
    print(f"\n  Hard residues (1,17): {hard_residues}/{len(survivors)} "
          f"({100*hard_residues/len(survivors):.1f}%)")

    # Prime factorization analysis
    print(f"\n--- Prime Factor Analysis ---")
    num_primes = sum(1 for n in survivors if is_prime(n))
    print(f"  Primes: {num_primes}/{len(survivors)} ({100*num_primes/len(survivors):.1f}%)")

    factor_counts = Counter(len(prime_factors(n)) for n in survivors)
    print(f"  Factor count distribution (with multiplicity):")
    for k in sorted(factor_counts.keys()):
        pct = 100 * factor_counts[k] / len(survivors)
        print(f"    {k} factors: {factor_counts[k]:,} ({pct:.1f}%)")

    # Smallest prime factor distribution
    print(f"\n  Smallest prime factor distribution:")
    spf = Counter(smallest_prime_factor(n) for n in survivors)
    for p in sorted(spf.keys())[:10]:
        pct = 100 * spf[p] / len(survivors)
        print(f"    spf={p}: {spf[p]:,} ({pct:.1f}%)")

    # Largest prime factor analysis
    print(f"\n  Largest prime factor / n ratio:")
    ratios = []
    for n in survivors:
        pf = prime_factors(n)
        if pf:
            ratios.append(max(pf) / n)
    if ratios:
        ratios.sort()
        print(f"    Min:    {ratios[0]:.6f}")
        print(f"    Median: {ratios[len(ratios)//2]:.6f}")
        print(f"    Mean:   {sum(ratios)/len(ratios):.6f}")
        print(f"    Max:    {ratios[-1]:.6f}")

    # Offset analysis: how far is ceil(n/4) from a useful x?
    print(f"\n--- Offset-1 Analysis ---")
    x_min_works = 0
    for n in survivors:
        x = math.ceil(n / 4)
        num_r = 4 * x - n
        if num_r > 0:
            den_r = n * x
            if den_r % num_r == 0:
                x_min_works += 1
    print(f"  ceil(n/4) gives integer remainder: {x_min_works}/{len(survivors)}")

    # Print first 50 survivors
    print(f"\n--- First 50 Survivors ---")
    for n in survivors[:50]:
        pf = prime_factors(n)
        print(f"  n={n:>12,}  mod24={n%24:2d}  factors={pf}")

    # Print last 10
    if len(survivors) > 50:
        print(f"\n--- Last 10 Survivors ---")
        for n in survivors[-10:]:
            pf = prime_factors(n)
            print(f"  n={n:>12,}  mod24={n%24:2d}  factors={pf}")

    return survivors


def main():
    unsolved_file = sys.argv[1] if len(sys.argv) >= 2 else "unsolved_ns.txt"
    results_dir = sys.argv[2] if len(sys.argv) >= 3 else "."

    print(f"Loading unsolved list from {unsolved_file}...")
    with open(unsolved_file) as f:
        all_unsolved = set(int(line.strip()) for line in f if line.strip())
    print(f"  {len(all_unsolved):,} unsolved values")

    print(f"\nLoading solved values from rescue results...")
    solved = load_solved_ns(results_dir)
    print(f"\n  Total unique solved: {len(solved):,}")

    survivors = all_unsolved - solved
    print(f"  Survivors (unsolved after all rescue): {len(survivors):,}")
    print(f"  Rescue success rate: {100*(1 - len(survivors)/len(all_unsolved)):.4f}%")

    profile_survivors(survivors)


if __name__ == "__main__":
    main()
