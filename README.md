# Erdos-Straus Conjecture Solver

**Guinea Pig Trench LLC**

Verifies the [Erdos-Straus conjecture](https://en.wikipedia.org/wiki/Erd%C5%91s%E2%80%93Straus_conjecture) for all integers n = 2..20,000,000 by finding positive integer decompositions:

```
4/n = 1/x + 1/y + 1/z    where x <= y <= z
```

[Live Dashboard](https://commencethescourge.github.io/erdos-straus-solver/erdos_dashboard.html)

## Results

**1,666,666 hard-residue targets (n mod 24 in {1, 17}) fully solved across n=2..20,000,000.** All other residue classes have known parametric families and are trivially solvable.

- Stage 1 (hunter): 1,491,274/1,666,666 solved with 500K step cap (89.5%)
- Stage 2 (leviathan): remaining 175,392 solved with 50M step cap (100%)
- 97.5% of solved nodes have z > 10^14
- Max z found: 22 digits (at n=999,985 in the 1M dataset)
- Total pipeline runtime: ~3.2 hours for 20M range

### Scaling behavior

| Range | Hard targets | Hunter rate | Leviathan count | Time |
|-------|-------------|------------|-----------------|------|
| n=2..50K | 4,166 | 86.4% | 565 | 24s |
| n=2..1M | 83,332 | 88.7% | 9,381 | 9.4 min |
| n=2..20M | 1,666,666 | 89.5% | 175,392 | 3.2h |

## Architecture

### Two-stage pipeline

1. **Hunter** (Stage 1) — Scans the target range, filtering to only the hard residue classes (n mod 24 in {1, 17}). Uses a 500K global step cap with multiprocessing.

2. **Leviathan Autopsy** (Stage 2) — Retries unsolved nodes from Stage 1 with a 50M step cap.

### Key solver insight

The naive approach iterates over all (x, y) pairs with a single global step budget. For hard cases, the solver would exhaust millions of steps on the y-range of a single x value (typically x = ceil(n/4)) without finding a valid z.

The fix: a **per-x y-iteration cap** (`y_cap_per_x`, default 1M). This lets the solver skip to the next x offset when a given x's y-range is unproductive. Solutions are almost always found at x = ceil(n/4) + 1 with very few y-iterations.

Across all leviathans, **86.8% solve at offset 1** (x = ceil(n/4) + 1), with a mean offset of 1.24. This pattern holds from n=2 through n=20,000,000.

### Checkpoint system

Results are saved atomically via `tempfile.mkstemp()` + `os.replace()`, so checkpoint files are never left in a half-written state. The pipeline resumes cleanly from existing checkpoints.

### CSV safety

Integer values exceeding 15 digits are wrapped in `=""` format to prevent Excel/Sheets truncation. A pre-tool-use hook enforces this at write time. This is critical — 97.5% of solutions have z values exceeding 10^14.

## Files

| File | Description |
|------|-------------|
| `erdos_straus.py` | Solver module with pipeline stages |
| `tests/test_solver.py` | Test suite (23 tests) |
| `erdos_dashboard.html` | Interactive results dashboard |
| `hunter_20M_checkpoint.csv` | Stage 1 results for n=2..20M (1,666,666 rows) |
| `leviathan_20M_checkpoint.csv` | Stage 2 results for n=2..20M (175,392 rows) |
| `hunter_1M_checkpoint.csv` | Stage 1 results for n=2..1M (83,332 rows) |
| `leviathan_1M_checkpoint.csv` | Stage 2 results for n=2..1M (9,381 rows) |
| `hunter_checkpoint.csv` | Stage 1 results for n=2..50K (4,166 rows) |
| `leviathan_checkpoint.csv` | Stage 2 results for n=2..50K (565 rows) |
| `pyproject.toml` | pytest configuration |

## Usage

```bash
# Run the full pipeline
python erdos_straus.py

# Run tests
pytest tests/

# Use the solver programmatically
from erdos_straus import solve_single
sol, steps = solve_single(n=1009, step_cap=500_000)
```

## Requirements

- Python 3.10+
- No external dependencies (stdlib only)
- Optional: `black` (code formatting), `pytest` (testing)
