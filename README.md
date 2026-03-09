# Erdos-Straus Conjecture Solver

**Guinea Pig Trench LLC**

Verifies the [Erdos-Straus conjecture](https://en.wikipedia.org/wiki/Erd%C5%91s%E2%80%93Straus_conjecture) for all integers n = 2..50,000 by finding positive integer decompositions:

```
4/n = 1/x + 1/y + 1/z    where x <= y <= z
```

## Results

**4,166 hard-residue targets (n mod 24 in {1, 17}) fully solved.** All other residue classes have known parametric families and are trivially solvable.

- Stage 1 (hunter): 3,601/4,166 solved with 500K step cap
- Stage 2 (leviathan): remaining 565 solved with 5M-50M step caps
- Largest z found: 57,568,265,007,348 (14 digits, n=38329)
- Total pipeline runtime: ~30 seconds on a modern machine

## Architecture

### Two-stage pipeline

1. **Hunter** (Stage 1) — Scans n=2..50,000, filtering to only the hard residue classes (n mod 24 in {1, 17}). Uses a 500K global step cap with multiprocessing.

2. **Leviathan Autopsy** (Stage 2) — Retries unsolved nodes from Stage 1 with a higher step cap (5M default).

### Key solver insight

The naive approach iterates over all (x, y) pairs with a single global step budget. For hard cases, the solver would exhaust millions of steps on the y-range of a single x value (typically x = ceil(n/4)) without finding a valid z.

The fix: a **per-x y-iteration cap** (`y_cap_per_x`, default 1M). This lets the solver skip to the next x offset when a given x's y-range is unproductive. Solutions are almost always found at x = ceil(n/4) + 1 with very few y-iterations.

This single change improved the leviathan solve rate from 73/565 to 558/565 at the same 5M global cap.

### Checkpoint system

Results are saved atomically via `tempfile.mkstemp()` + `os.replace()`, so checkpoint files are never left in a half-written state. The pipeline resumes cleanly from existing checkpoints.

### CSV safety

Integer values exceeding 15 digits are wrapped in `=""` format to prevent Excel/Sheets truncation. A pre-tool-use hook enforces this at write time.

## Files

| File | Description |
|------|-------------|
| `erdos_straus.py` | Solver module with pipeline stages |
| `tests/test_solver.py` | Test suite (23 tests) |
| `hunter_checkpoint.csv` | Stage 1 results (4,166 rows) |
| `leviathan_checkpoint.csv` | Stage 2 results (565 rows) |
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
