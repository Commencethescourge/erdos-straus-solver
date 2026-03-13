# Erdos-Straus Conjecture Solver

**Guinea Pig Trench LLC**

Verifies the [Erdos-Straus conjecture](https://en.wikipedia.org/wiki/Erd%C5%91s%E2%80%93Straus_conjecture) — that for every integer n >= 2, the equation 4/n = 1/x + 1/y + 1/z has a solution in positive integers.

```
4/n = 1/x + 1/y + 1/z    for all n >= 2
```

## Current Record

**Verified to 10^14 (100 trillion). Zero counterexamples.**

Achieved via modular sieve across free-tier Kaggle compute. Based on the method of Salez (2014) and Mihnea & Dumitru (2025, arXiv:2509.00128).

## Method: Modular Sieve

The sieve works by eliminating candidate counterexamples modulo small primes. The sieve modulus is:

```
G_8 = 2^3 * 3^2 * 5 * 7 * 11 * 13 * 17 * 19 = 25,878,772,920
```

For each batch k, the sieve checks all residues r in a precomputed set (~2.1M residues) to see if n = r + k * G_8 survives a cascade of modular filters. Any survivor is then primality-tested — only prime survivors would be potential counterexamples.

**Result: zero prime survivors across all 3,865 batches (k=0 to k=3864).**

### Sieve Performance

| Range | Batches | Platform | Prime Survivors |
|-------|---------|----------|-----------------|
| k=0-966 | 967 | Kaggle | 0 |
| k=967-1545 | 579 | Kaggle | 0 |
| k=1546-2318 | 773 | Kaggle | 0 |
| k=2319-3091 | 773 | Kaggle | 0 |
| k=3092-3478 | 387 | Kaggle | 0 |
| k=3479-3864 | 386 | Kaggle | 0 |
| **Total** | **3,865** | | **0** |

## Prior Work: Brute-Force Pipeline (n=2 to 100M)

Before the modular sieve, the first 100 million integers were verified via a three-stage CPU/GPU pipeline:

1. **Hunter** — Scans hard residue classes (n mod 24 in {1, 17}) with a 500K step cap
2. **Leviathan** — Retries unsolved cases with a 50M step cap
3. **GPU Rescue** — Cracks final holdouts via OpenCL (79 holdouts solved in 2.5s)

Key finding: **85.6% of hard cases solve at offset 1** (x = ceil(n/4) + 1), from n=2 through n=100M.

## Distributed Cloud Architecture

All sieve work runs on free cloud compute with zero budget:

| Platform | Cores | RAM | Session | Status |
|----------|-------|-----|---------|--------|
| **Kaggle** | 4 | 29GB | 12hr background | Primary — completed 10^14 |
| Google Colab | 2 | 12GB | 12hr | Too slow on free tier |
| Lightning.ai | 4 | 16GB | Always-on | Auto-sleeps, loses progress |
| SageMaker | 4 | 16GB | 12hr | Backup |
| Phone (Termux) | 8 | 4GB | Always-on | Experimental |

### Lessons Learned

- Kaggle is the only reliable free platform for unattended batch compute
- Modular sieve produces tiny CSVs vs 500MB brute-force checkpoints
- `chunksize=1` for `imap_unordered` is critical for progress visibility
- Auto-resume via CSV checkpoint saved every restart

## Files

| File | Description |
|------|-------------|
| **Core** | |
| `erdos_straus.py` | CPU solver (brute-force pipeline) |
| `erdos_straus_gpu.py` | GPU solver (OpenCL) |
| **Sieve** | |
| `sieve_data/Residues.txt` | Precomputed sieve residues (~2.1M) |
| `sieve_data/Filters.txt` | Modular filter cascade |
| `kaggle_deploy2/` | Kaggle sieve notebook #1 |
| `kaggle_deploy3/` | Kaggle sieve notebook #2 |
| **Cloud** | |
| `erdos_straus_sieve_lightning.py` | Lightning.ai sieve script |
| `erdos_straus_sieve_kaggle.ipynb` | Kaggle sieve notebook (original) |
| `cloud_coordinator.py` | Range splitting, merging, status |
| **Results** | |
| `kaggle_results/sieve_results_*.csv` | Sieve output — 6 files covering k=0-3864 |
| `final_rescue_results.csv` | GPU rescue results (brute-force era) |
| **Tools** | |
| `erdos_dashboard.html` | Interactive results dashboard |
| `tests/` | Test suite |

## Next Milestone

**10^17** — 3.86 million batches. Requires coordinated queue (Google Sheet job queue planned) across multiple concurrent Kaggle sessions.

## Usage

```bash
# Run brute-force pipeline (local, up to 100M)
python erdos_straus.py

# Run tests
pytest tests/

# Distribute sieve work
python cloud_coordinator.py split <start> <end> <platforms>
python cloud_coordinator.py status
python cloud_coordinator.py merge
```

## Requirements

- Python 3.10+
- Sieve solver: no external dependencies (stdlib only)
- GPU solver: `pyopencl`, `numpy`
- Cloud notebooks: zero dependencies (self-contained)

## References

- Salez, T. (2014). "The Erdos-Straus conjecture: New modular equations and checking up to 10^17"
- Mihnea, A. & Dumitru, V. (2025). arXiv:2509.00128
