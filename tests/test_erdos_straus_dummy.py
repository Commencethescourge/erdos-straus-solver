"""Dummy tests for the Erdős–Straus conjecture project."""

from fractions import Fraction


def test_known_solution_n5():
    """4/5 = 1/2 + 1/4 + 1/20"""
    n = 5
    x, y, z = 2, 4, 20
    assert Fraction(1, x) + Fraction(1, y) + Fraction(1, z) == Fraction(4, n)


def test_known_solution_n7():
    """4/7 = 1/2 + 1/14 (third fraction absorbed: 1/2 + 1/14 + 1/14 is not valid,
    but 4/7 = 1/2 + 1/14 holds as a two-term decomposition)."""
    n = 7
    x, y = 2, 14
    assert Fraction(1, x) + Fraction(1, y) == Fraction(4, n)


def test_mod24_leviathan_classification():
    """Residues mod 24 that are known to always have simple decompositions.
    For n ≡ 0 (mod 4), a trivial decomposition exists: 4/n = 1/(n/4) + 1/∞ ...
    More usefully, if n ≡ 0 (mod 4): 4/n = 4/n with x=y=z=3n/4 style.
    Verify that every residue class mod 24 is covered by at least one case."""
    covered_residues = set()
    for n in range(2, 26):
        # Try brute-force decomposition 4/n = 1/x + 1/y + 1/z
        target = Fraction(4, n)
        found = False
        for x in range(1, 4 * n):
            for y in range(x, 4 * n):
                remainder = target - Fraction(1, x) - Fraction(1, y)
                if remainder > 0 and remainder.numerator == 1:
                    covered_residues.add(n % 24)
                    found = True
                    break
            if found:
                break
    # All residues 2..23 should be covered (0 and 1 don't appear for n>=2 in this range)
    expected = {n % 24 for n in range(2, 26)}
    assert expected == covered_residues


def test_csv_integer_safety_round_trip():
    """Large integers must be wrapped in ="" for CSV to survive Excel round-trip."""
    large_int = 12345678901234567
    csv_safe = f'="{large_int}"'
    assert csv_safe == '="12345678901234567"'
    # Verify the raw value is recoverable by stripping the wrapper
    recovered = int(csv_safe.lstrip('="').rstrip('"'))
    assert recovered == large_int


def test_placeholder():
    assert True
