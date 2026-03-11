# Tests for GPU-accelerated Erdos-Straus solver
"""Validates GPU solver correctness against known CPU results."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from erdos_straus import solve_single, Solution
from io_safety import csv_safe, csv_unsafe

# Skip all tests if no GPU available
try:
    from erdos_straus_gpu import gpu_solve_batch, create_gpu_context
    ctx, dev = create_gpu_context()
    GPU_AVAILABLE = True
except Exception:
    GPU_AVAILABLE = False

pytestmark = pytest.mark.skipif(not GPU_AVAILABLE, reason="No OpenCL GPU available")


def _verify_solution(n, x, y, z):
    """Verify 4/n == 1/x + 1/y + 1/z using integer arithmetic."""
    lhs = 4 * x * y * z
    rhs = n * (y * z + x * z + x * y)
    return lhs == rhs and x <= y <= z


def _parse_result(r):
    """Extract integers from a GPU result dict."""
    x = int(csv_unsafe(str(r["x"])))
    y = int(csv_unsafe(str(r["y"])))
    z = int(csv_unsafe(str(r["z"])))
    return x, y, z


class TestGPUSolverCorrectness:
    """Verify GPU solutions are mathematically valid."""

    def test_small_known_values(self):
        ns = [5, 7, 11, 13, 17, 19, 23, 29, 31, 37]
        results = gpu_solve_batch(ns, step_cap=500_000, ctx=ctx)
        for r in results:
            assert r["solved"], f"n={r['n']} not solved"
            x, y, z = _parse_result(r)
            assert _verify_solution(r["n"], x, y, z), f"Invalid for n={r['n']}"

    def test_hard_mod24_residues(self):
        """n values where n%24 in {1,17} -- the hard cases."""
        ns = [25, 41, 49, 73, 97, 121, 169, 193, 217, 241]
        results = gpu_solve_batch(ns, step_cap=500_000, ctx=ctx)
        for r in results:
            assert r["solved"], f"Hard residue n={r['n']} not solved"
            x, y, z = _parse_result(r)
            assert _verify_solution(r["n"], x, y, z)

    def test_gpu_matches_cpu(self):
        """GPU and CPU must produce valid solutions for same inputs."""
        ns = [5, 25, 49, 97, 193, 337, 433, 577, 769, 953]
        gpu_results = gpu_solve_batch(ns, step_cap=500_000, ctx=ctx)
        for r in gpu_results:
            n = r["n"]
            cpu_sol, _ = solve_single(n, 500_000)
            assert r["solved"] == (cpu_sol is not None), f"Mismatch at n={n}"
            if r["solved"]:
                x, y, z = _parse_result(r)
                assert _verify_solution(n, x, y, z)

    def test_n_equals_1_impossible(self):
        results = gpu_solve_batch([1], step_cap=500_000, ctx=ctx)
        assert not results[0]["solved"]

    def test_even_values_trivial(self):
        """Even n should be trivially solvable."""
        ns = [2, 4, 6, 8, 10, 100, 200, 500, 1000]
        results = gpu_solve_batch(ns, step_cap=500_000, ctx=ctx)
        for r in results:
            assert r["solved"], f"Even n={r['n']} not solved"
            x, y, z = _parse_result(r)
            assert _verify_solution(r["n"], x, y, z)

    def test_batch_100_all_valid(self):
        """Solve n=2..100 and verify every solution."""
        ns = list(range(2, 101))
        results = gpu_solve_batch(ns, step_cap=500_000, ctx=ctx)
        for r in results:
            assert r["solved"], f"n={r['n']} not solved"
            x, y, z = _parse_result(r)
            assert _verify_solution(r["n"], x, y, z), f"Invalid for n={r['n']}"

    def test_ordering_constraint(self):
        """All solutions must satisfy x <= y <= z."""
        ns = list(range(2, 201))
        results = gpu_solve_batch(ns, step_cap=500_000, ctx=ctx)
        for r in results:
            if r["solved"]:
                x, y, z = _parse_result(r)
                assert x <= y <= z, f"Ordering violated for n={r['n']}: {x},{y},{z}"


class TestGPUBatchMechanics:
    """Test batch dispatch and edge cases."""

    def test_single_item_batch(self):
        results = gpu_solve_batch([5], step_cap=500_000, ctx=ctx)
        assert len(results) == 1
        assert results[0]["solved"]

    def test_large_batch(self):
        """Test a batch larger than one GPU dispatch."""
        ns = [n for n in range(2, 5001) if (n % 24) in {1, 17}]
        results = gpu_solve_batch(ns, step_cap=500_000, ctx=ctx)
        solved = sum(1 for r in results if r["solved"])
        assert solved > len(ns) * 0.80, f"Only {solved}/{len(ns)} solved"

    def test_step_cap_respected(self):
        """With a tiny step cap, some values should remain unsolved."""
        ns = [49, 73, 169, 193, 241]  # known to need many steps
        results = gpu_solve_batch(ns, step_cap=10, ctx=ctx)
        unsolved = sum(1 for r in results if not r["solved"])
        assert unsolved > 0, "Step cap of 10 should leave some unsolved"

    def test_result_format(self):
        """Verify output dict has all expected keys."""
        results = gpu_solve_batch([5], step_cap=500_000, ctx=ctx)
        r = results[0]
        assert "n" in r
        assert "x" in r
        assert "y" in r
        assert "z" in r
        assert "steps" in r
        assert "solved" in r
