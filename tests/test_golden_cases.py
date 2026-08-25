"""Golden-fixture suite: every YAML case must pass byte-for-byte."""
from tests.harness import all_cases, run_case


def test_all_golden_cases():
    failures: list[str] = []
    for path in all_cases():
        failures.extend(run_case(path))
    assert not failures, "\n".join(failures)


def test_fixture_count_pinned():
    # Guard against silently dropping coverage (DESIGN.md targets 8+ cases).
    assert len(all_cases()) >= 8
