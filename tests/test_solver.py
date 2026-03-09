"""Tests for the Erdős–Straus solver module."""

import csv
import os
import tempfile
from fractions import Fraction

from erdos_straus import (
    Solution,
    csv_safe,
    load_checkpoint,
    save_checkpoint,
    solve_single,
    _needs_compute,
    _worker,
    CSV_FIELDS,
)


# ---------------------------------------------------------------------------
# solve_single — correctness
# ---------------------------------------------------------------------------


def _verify(n: int, x: int, y: int, z: int) -> None:
    """Assert 4/n == 1/x + 1/y + 1/z exactly."""
    assert Fraction(1, x) + Fraction(1, y) + Fraction(1, z) == Fraction(4, n)


def test_solve_small_values():
    """Solver finds valid decompositions for small n."""
    for n in range(2, 100):
        sol, steps = solve_single(n, step_cap=100_000)
        assert sol is not None, f"no solution for n={n}"
        _verify(n, sol.x, sol.y, sol.z)
        assert sol.x <= sol.y <= sol.z


def test_solve_known_n5():
    sol, _ = solve_single(5, step_cap=10_000)
    assert sol is not None
    _verify(5, sol.x, sol.y, sol.z)


def test_solve_known_n7():
    sol, _ = solve_single(7, step_cap=10_000)
    assert sol is not None
    _verify(7, sol.x, sol.y, sol.z)


def test_solve_n1_impossible():
    """n=1 means 4 = 1/x+1/y+1/z which is impossible for positive ints."""
    sol, _ = solve_single(1, step_cap=10_000)
    assert sol is None


def test_solve_step_cap_respected():
    """Solver should stop within the step cap."""
    _, steps = solve_single(9999991, step_cap=100)
    assert steps <= 100


def test_solve_hard_mod24_residues():
    """Test a few n ≡ 1 and 17 (mod 24) — the 'hard' residues."""
    for n in [25, 41, 49, 73, 97]:
        sol, _ = solve_single(n, step_cap=500_000)
        assert sol is not None, f"failed for n={n}"
        _verify(n, sol.x, sol.y, sol.z)


# ---------------------------------------------------------------------------
# csv_safe — str(z) firewall
# ---------------------------------------------------------------------------


def test_csv_safe_small():
    assert csv_safe(12345) == "12345"


def test_csv_safe_exactly_15_digits():
    val = 123456789012345  # 15 digits
    assert csv_safe(val) == "123456789012345"


def test_csv_safe_16_digits():
    val = 1234567890123456  # 16 digits
    assert csv_safe(val) == '="1234567890123456"'


def test_csv_safe_large():
    val = 4670000000000000000
    assert csv_safe(val) == '="4670000000000000000"'


def test_csv_safe_roundtrip():
    """Values wrapped in ="" can be recovered."""
    val = 99999999999999999
    wrapped = csv_safe(val)
    recovered = int(wrapped.lstrip('="').rstrip('"'))
    assert recovered == val


# ---------------------------------------------------------------------------
# mod24 filter
# ---------------------------------------------------------------------------


def test_needs_compute_filter():
    targets = {1, 17}
    assert _needs_compute(1, targets)  # 1 % 24 == 1
    assert _needs_compute(17, targets)  # 17 % 24 == 17
    assert _needs_compute(25, targets)  # 25 % 24 == 1
    assert _needs_compute(41, targets)  # 41 % 24 == 17
    assert not _needs_compute(2, targets)
    assert not _needs_compute(24, targets)
    assert not _needs_compute(5, targets)


# ---------------------------------------------------------------------------
# _worker
# ---------------------------------------------------------------------------


def test_worker_solved():
    result = _worker((5, 10_000, "test_run"))
    assert result["solved"] is True
    assert result["run_id"] == "test_run"
    assert result["n"] == 5


def test_worker_unsolvable():
    result = _worker((1, 100, "test_run"))
    assert result["solved"] is False
    assert result["x"] == ""


# ---------------------------------------------------------------------------
# Checkpoint I/O
# ---------------------------------------------------------------------------


def test_checkpoint_round_trip():
    """save → load round-trip preserves data."""
    results = {
        5: {
            "n": 5,
            "x": "2",
            "y": "4",
            "z": "20",
            "steps": 3,
            "solved": "True",
            "run_id": "abc123",
        },
        7: {
            "n": 7,
            "x": "2",
            "y": "7",
            "z": "14",
            "steps": 5,
            "solved": "True",
            "run_id": "abc123",
        },
    }
    with tempfile.NamedTemporaryFile(
        suffix=".csv", delete=False, mode="w"
    ) as tmp:
        tmp_path = tmp.name

    try:
        save_checkpoint(tmp_path, results)
        loaded = load_checkpoint(tmp_path)
        assert set(loaded.keys()) == {5, 7}
        assert loaded[5]["z"] == "20"
        assert loaded[7]["run_id"] == "abc123"
    finally:
        os.unlink(tmp_path)


def test_checkpoint_atomic_replace():
    """os.replace() means the file is never in a half-written state."""
    with tempfile.NamedTemporaryFile(
        suffix=".csv", delete=False, mode="w"
    ) as tmp:
        tmp_path = tmp.name

    try:
        # Write initial
        results = {
            2: {
                "n": 2,
                "x": "1",
                "y": "2",
                "z": "2",
                "steps": 1,
                "solved": "True",
                "run_id": "r1",
            }
        }
        save_checkpoint(tmp_path, results)

        # Overwrite
        results[3] = {
            "n": 3,
            "x": "1",
            "y": "4",
            "z": "12",
            "steps": 2,
            "solved": "True",
            "run_id": "r2",
        }
        save_checkpoint(tmp_path, results)

        loaded = load_checkpoint(tmp_path)
        assert len(loaded) == 2
    finally:
        os.unlink(tmp_path)


def test_load_checkpoint_missing_file():
    """Loading a nonexistent checkpoint returns empty dict."""
    result = load_checkpoint("/nonexistent/path/foo.csv")
    assert result == {}


# ---------------------------------------------------------------------------
# CSV output format validation
# ---------------------------------------------------------------------------


def test_csv_output_no_raw_large_ints():
    """Verify that CSV output never contains raw integers >15 digits."""
    results = {}
    # Manufacture a result with a large z
    big_z = 9999999999999999  # 16 digits
    results[101] = {
        "n": 101,
        "x": "26",
        "y": "2626",
        "z": csv_safe(big_z),
        "steps": 42,
        "solved": "True",
        "run_id": "test",
    }

    with tempfile.NamedTemporaryFile(
        suffix=".csv", delete=False, mode="w"
    ) as tmp:
        tmp_path = tmp.name

    try:
        save_checkpoint(tmp_path, results)
        with open(tmp_path, encoding="utf-8") as f:
            content = f.read()
        # No raw 16+ digit integers outside ="" wrappers
        import re

        # Find all numbers that are 16+ digits and NOT inside =""
        for line in content.split("\n"):
            if not line or line.startswith("n,"):
                continue
            fields = line.split(",")
            for field in fields:
                stripped = field.strip()
                if stripped.startswith('="') and stripped.endswith('"'):
                    continue
                if stripped.isdigit() and len(stripped) > 15:
                    raise AssertionError(
                        f"Raw large integer in CSV: {stripped}"
                    )
    finally:
        os.unlink(tmp_path)
