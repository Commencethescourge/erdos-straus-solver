# Erdos-Straus Conjecture Solver

**Guinea Pig Trench LLC**

Verifies the [Erdos-Straus conjecture](https://en.wikipedia.org/wiki/Erd%C5%91s%E2%80%93Straus_conjecture) for all integers n = 2..100,000,000 by finding positive integer decompositions:

```
4/n = 1/x + 1/y + 1/z    where x <= y <= z
```

[Live Dashboard](https://commencethescourge.github.io/erdos-straus-solver/erdos_dashboard.html)

## Results

**8,333,332 hard-residue targets (n mod 24 in {1, 17}) fully solved across n=2..100,000,000.** All other residue classes have known parametric families and are trivially solvable. Zero unsolved values remain.

- n=2..20M solved via two-stage CPU pipeline (hunter + leviathan)
- n=20M..100M solved via chunked CPU rescue passes + GPU-accelerated final rescue
- 79 stubborn holdouts (10M step cap failures) cracked by GPU in 2.5 seconds
- Max z found: 30 digits; largest z values cluster near n~20M
- Across all leviathans, **85.6% solve at offset 1** (x = ceil(n/4) + 1)

### Scaling behavior

| Range | Hard targets | Hunter rate | Leviathan count | Time |
|-------|-------------|------------|-----------------|------|
| n=2..50K | 4,166 | 86.4% | 565 | 24s |
| n=2..1M | 83,332 | 88.7% | 9,381 | 9.4 min |
| n=2..20M | 1,666,666 | 89.5% | 175,392 | 3.2h |
| n=20M..100M | 6,666,666 | ~89% | ~460,709 | chunked |

## Architecture

### Three-stage pipeline

1. **Hunter** (Stage 1) — Scans the target range, filtering to only the hard residue classes (n mod 24 in {1, 17}). Uses a 500K global step cap with CPU multiprocessing.

2. **Leviathan Autopsy** (Stage 2) — Retries unsolved nodes from Stage 1 with a 50M step cap.

3. **GPU Rescue** (Stage 3) — Cracks remaining holdouts via OpenCL on AMD Radeon RX 6400 (RDNA 2). The 79 final holdouts that survived 10M CPU step caps were solved in 2.5 seconds on GPU with a 100M step cap.

### Key solver insight

The naive approach iterates over all (x, y) pairs with a single global step budget. For hard cases, the solver would exhaust millions of steps on the y-range of a single x value (typically x = ceil(n/4)) without finding a valid z.

The fix: a **per-x y-iteration cap** (`y_cap_per_x`, default 1M). This lets the solver skip to the next x offset when a given x's y-range is unproductive. Solutions are almost always found at x = ceil(n/4) + 1 with very few y-iterations.

Across all leviathans, **85.6% solve at offset 1** (x = ceil(n/4) + 1). This pattern holds from n=2 through n=100,000,000.

### Checkpoint system

Results are saved atomically via `tempfile.mkstemp()` + `os.replace()`, so checkpoint files are never left in a half-written state. The pipeline resumes cleanly from existing checkpoints.

### CSV safety

Integer values exceeding 15 digits are wrapped in `=""` format to prevent Excel/Sheets truncation. A pre-tool-use hook enforces this at write time. This is critical — 97.5% of solutions have z values exceeding 10^14.

## Distributed Cloud Solving

Push the frontier beyond 100M using free cloud compute. All solvers are self-contained (zero dependencies), auto-resume on crash, and use a 20M step cap.

| Platform | File | Cores | RAM | Session | Notes |
|----------|------|-------|-----|---------|-------|
| **Kaggle** | `erdos_straus_kaggle.ipynb` | 4 | 29GB | 12hr | Background execution — keeps running when tab is closed |
| **Google Colab** | `erdos_straus_colab.ipynb` | 2 | 12GB | 12hr | Saves to Google Drive |
| **Lightning.ai** | `erdos_straus_lightning.py` | 4 | 16GB | Always-on | Full terminal, run with tmux |
| **SageMaker Studio Lab** | `erdos_straus_sagemaker.ipynb` | 4 | 16GB | 12hr | Persistent storage across sessions |
| **Phone (Termux)** | `phone_solver_v2.py` | 8 | 4GB | Always-on | Wake lock + tmux for 24/7 solving |

### Coordinator

Split ranges across platforms and merge results:

```bash
# Split the next 100M across 5 platforms
python cloud_coordinator.py split 100000001 200000000 5

# Check progress across all result files
python cloud_coordinator.py status

# Merge all results into combined_results.csv
python cloud_coordinator.py merge
```

## Files

| File | Description |
|------|-------------|
| **Core solvers** | |
| `erdos_straus.py` | CPU solver module with two-stage pipeline |
| `erdos_straus_gpu.py` | GPU-accelerated solver (OpenCL, AMD RDNA 2) |
| `final_rescue.py` | GPU+CPU rescue for stubborn holdouts |
| `cpu_rescue.py` | CPU rescue worker for chunked processing |
| `auto_rescue.py` | Coordinator that chains CPU rescue chunks |
| **Cloud solvers** | |
| `erdos_straus_colab.ipynb` | Google Colab notebook |
| `erdos_straus_kaggle.ipynb` | Kaggle notebook |
| `erdos_straus_lightning.py` | Lightning.ai terminal script |
| `erdos_straus_sagemaker.ipynb` | SageMaker Studio Lab notebook |
| `cloud_coordinator.py` | Split ranges, merge results, check status |
| **Phone solvers** | |
| `phone_solver.py` | Termux CPU solver v1 |
| `phone_solver_v2.py` | Termux CPU solver v2 (auto-resume, 20M cap) |
| `phone_gpu_solver.c` | Adreno OpenCL C solver |
| **Analysis & tools** | |
| `colab_rescue.py` | Legacy Colab rescue script |
| `survivor_profile.py` | Structural analysis of unsolved values |
| `erdos_dashboard.html` | Interactive results dashboard |
| `tests/` | Test suite (34 tests: CPU, GPU, integration) |
| **Data** | |
| `hunter_20M_checkpoint.csv` | Stage 1 results for n=2..20M (1,666,666 rows) |
| `leviathan_20M_checkpoint.csv` | Stage 2 results for n=2..20M (175,392 rows) |
| `cpu_rescue{3-8}_results.csv` | Rescue results for n=20M..100M (~2.7M rows) |
| `final_rescue_results.csv` | Final 79 holdouts solved by GPU |

## Usage

```bash
# Run the full pipeline (local)
python erdos_straus.py

# Run tests
pytest tests/

# Use the solver programmatically
from erdos_straus import solve_single
sol, steps = solve_single(n=1009, step_cap=500_000)

# Distribute work across cloud platforms
python cloud_coordinator.py split 100000001 200000000 5
```

## Requirements

- Python 3.10+
- CPU solver: no external dependencies (stdlib only)
- GPU solver: `pyopencl`, `numpy`
- Cloud notebooks: zero dependencies (everything is self-contained)
- Optional: `black` (code formatting), `pytest` (testing)
