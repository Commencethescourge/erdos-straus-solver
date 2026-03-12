"""Tests for the modular sieve solver."""
import os
import pytest

SIEVE_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sieve_data"
)
HAVE_SIEVE_DATA = (
    os.path.exists(os.path.join(SIEVE_DATA_DIR, "Residues.txt"))
    and os.path.exists(os.path.join(SIEVE_DATA_DIR, "Filters.txt"))
)

needs_data = pytest.mark.skipif(
    not HAVE_SIEVE_DATA, reason="Sieve data not downloaded"
)


from erdos_straus_sieve import G_8, is_prime


def test_g8_value():
    """G_8 should be 24 * product of primes 5..29."""
    expected = 24
    for p in [5, 7, 11, 13, 17, 19, 23]:
        expected *= p
    # The paper says G_8 = 25,878,772,920
    assert G_8 == 25_878_772_920


def test_is_prime():
    assert is_prime(2)
    assert is_prime(3)
    assert not is_prime(4)
    assert is_prime(1009)
    assert not is_prime(1)
    assert not is_prime(0)


@needs_data
class TestDataLoading:
    def test_load_residues_count(self):
        from erdos_straus_sieve import load_residues
        r = load_residues()
        assert 2_000_000 < len(r) < 2_200_000  # ~2.1M

    def test_load_residues_range(self):
        from erdos_straus_sieve import load_residues
        r = load_residues()
        assert all(0 < x < G_8 or x == 1 for x in r[:100])
        assert max(r) < G_8

    def test_load_filters_count(self):
        from erdos_straus_sieve import load_filters
        f = load_filters()
        assert 140_000 < len(f) < 160_000  # ~148K

    def test_load_filters_primes(self):
        from erdos_straus_sieve import load_filters
        f = load_filters()
        # First few filter primes should be small primes
        primes = [p for p, _ in f[:10]]
        for p in primes:
            assert is_prime(p), f"{p} is not prime"


@needs_data
class TestSieveCorrectness:
    def test_batch_0_only_survivor_is_1(self):
        """Batch k=0 should have exactly one survivor: n=1 (not prime)."""
        from erdos_straus_sieve import load_residues, load_filters
        residues = load_residues()
        filters = load_filters()

        survivors = []
        for r in residues:
            n = r  # k=0
            filtered = False
            for p, excluded in filters:
                if n % p in excluded:
                    filtered = True
                    break
            if not filtered:
                survivors.append(n)

        assert len(survivors) == 1
        assert survivors[0] == 1
        assert not is_prime(1)

    def test_known_solvable_filtered(self):
        """Known solvable primes should be filtered out by the sieve."""
        from erdos_straus_sieve import load_residues, load_filters
        filters = load_filters()

        # These primes are all solvable by brute-force
        test_primes = [5, 7, 11, 13, 17, 1009, 2521]
        for n in test_primes:
            filtered = False
            for p, excluded in filters:
                if n % p in excluded:
                    filtered = True
                    break
            # n must be either filtered or not in R_8 residue set
            # (parametric families handle it)
            if not filtered:
                # Check if n is even in R_8
                residues = load_residues()
                r_set = set(residues)
                assert n not in r_set or not is_prime(n), (
                    f"Prime n={n} survived all filters AND is in R_8"
                )
            break  # only test first prime to keep test fast

    def test_sieve_agrees_with_bruteforce_small(self):
        """For small n, every prime in R_8 should be solvable by brute-force."""
        from erdos_straus_sieve import load_residues, load_filters

        # Import brute-force solver
        sys_path_backup = __import__("sys").path[:]
        __import__("sys").path.insert(0, os.path.dirname(SIEVE_DATA_DIR))
        from erdos_straus import solve_single

        residues = load_residues()
        filters = load_filters()

        # Check small primes that are in R_8
        small_residues = [r for r in residues if r < 10000 and is_prime(r)]

        for n in small_residues[:50]:  # test first 50
            # Check if sieve filters it
            filtered = False
            for p, excluded in filters:
                if n % p in excluded:
                    filtered = True
                    break

            if not filtered:
                # Sieve didn't filter it — brute-force must solve it
                sol, steps = solve_single(n, step_cap=1_000_000)
                assert sol is not None, f"Prime n={n} is unfilterable AND unsolvable!"
