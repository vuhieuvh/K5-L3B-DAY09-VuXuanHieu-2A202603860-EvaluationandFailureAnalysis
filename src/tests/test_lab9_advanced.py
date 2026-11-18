"""M5-M7 self-check (Advanced/Expert). Run: python -m pytest -q -m student -o addopts= -k advanced
Public vectors only; the instructor grades with hidden ones."""
import copy
import math

import pytest

pytestmark = pytest.mark.student


@pytest.fixture(scope="module")
def stats():
    from lab9 import stats

    return stats


@pytest.mark.parametrize("n,c,k,want", [(5, 5, 5, 1.0), (5, 0, 1, 0.0), (5, 2, 1, 0.4), (10, 3, 3, 1 - 35 / 120)])
def test_pass_at_k(stats, n, c, k, want):
    assert math.isclose(stats.pass_at_k(n, c, k), want, abs_tol=1e-9)


@pytest.mark.parametrize("n,c,k,want", [(5, 5, 5, 1.0), (5, 4, 5, 0.0), (5, 4, 3, 0.4), (10, 8, 2, 28 / 45)])
def test_pass_hat_k(stats, n, c, k, want):
    assert math.isclose(stats.pass_hat_k(n, c, k), want, abs_tol=1e-9)


def test_pass_k_rejects_bad_args(stats):
    for args in [(5, 6, 1), (5, 2, 0), (3, 1, 4)]:
        with pytest.raises(ValueError):
            stats.pass_at_k(*args)


def _report(rows, metrics, items=4, seeds=(1, 2)):
    return {"manifest": {"eval_set_sha": "x", "items": items, "seeds": list(seeds)},
            "rows": rows, "metrics": metrics, "evaluator_failures": []}


ROWS = [{"item_id": f"E-{i:03d}", "seed": s, "pass_rate": True, "slices": ["denial"] if i < 2 else []}
        for i in range(4) for s in (1, 2)]
SPEC = {"eval_set_version": "v2", "metrics": [{"id": "pass_rate", "kind": "capability", "blocking": True,
                                               "threshold": {"min": 0.8}}]}


def test_integrity_flags_nan_and_dropped_rows():
    from lab9 import gate

    base = _report(copy.deepcopy(ROWS), {"pass_rate": 1.0})
    assert gate.integrity_check(base, base, SPEC) == []
    nan = _report(copy.deepcopy(ROWS), {"pass_rate": float("nan")})
    assert gate.integrity_check(nan, base, SPEC)
    dropped = _report(copy.deepcopy(ROWS[:-1]), {"pass_rate": 1.0})
    assert gate.integrity_check(dropped, base, SPEC)


def test_integrity_flags_loosened_spec():
    from lab9 import gate

    base = _report(copy.deepcopy(ROWS), {"pass_rate": 1.0})
    loose = copy.deepcopy(SPEC)
    loose["metrics"][0]["threshold"]["min"] = 0.5
    assert gate.integrity_check(base, base, loose, SPEC)
    assert gate.integrity_check(base, base, SPEC, SPEC) == []


def test_slice_check_blocks_a_slice_below_floor():
    from lab9 import gate

    base = _report(copy.deepcopy(ROWS), {"pass_rate": 1.0})
    rows = copy.deepcopy(ROWS)
    for r in rows:
        if "denial" in r["slices"] and r["seed"] == 1:
            r["pass_rate"] = False
    spec = dict(SPEC, slices=[{"name": "denial", "metric": "pass_rate", "min": 0.9, "blocking": True}])
    blocked, _ = gate.slice_check(_report(rows, {"pass_rate": 0.75}), base, spec)
    assert blocked == ["slice:denial/pass_rate"]


@pytest.mark.parametrize("tamper", ["duplicate", "grader_failure", "missing_grade", "slice_tag", "aggregate"])
def test_integrity_rejects_a_green_report_with_untrustworthy_evidence(tamper):
    from lab9 import gate

    base = _report(copy.deepcopy(ROWS), {"pass_rate": 1.0})
    candidate = copy.deepcopy(base)
    if tamper == "duplicate":
        candidate["rows"][0] = copy.deepcopy(candidate["rows"][1])
    elif tamper == "grader_failure":
        candidate["evaluator_failures"] = ["a failed evaluator"]
    elif tamper == "missing_grade":
        candidate["rows"][0].pop("pass_rate")
    elif tamper == "slice_tag":
        candidate["rows"][0]["slices"].clear()
    else:
        candidate["rows"][0]["pass_rate"] = False
    assert gate.integrity_check(candidate, base, SPEC)


def test_ratchet_detects_shifted_slice_definition():
    from lab9 import gate

    base = _report(copy.deepcopy(ROWS), {"pass_rate": 1.0})
    original = dict(SPEC, slices=[{"name": "denial", "metric": "pass_rate", "min": 0.9,
                                   "no_significant_drop": True, "blocking": True}])
    candidate = copy.deepcopy(original)
    candidate["slices"][0].pop("no_significant_drop")
    assert gate.integrity_check(base, base, candidate, original)


def test_integrity_blocks_forged_pass_hat_five():
    from lab9 import gate

    seeds = (11, 22, 33, 44, 55)
    rows = [{"item_id": f"E-{i:03d}", "seed": seed, "pass_rate": True}
            for i in range(4) for seed in seeds]
    base = _report(rows, {"pass_rate": 1.0, "pass_hat_5": 1.0}, seeds=seeds)
    candidate = copy.deepcopy(base)
    candidate["rows"][0]["pass_rate"] = False
    candidate["metrics"] = {"pass_rate": 0.95, "pass_hat_5": 0.75}
    spec = dict(SPEC, metrics=[*SPEC["metrics"],
                               {"id": "pass_hat_5", "blocking": True, "threshold": {"min": 0.8}}])
    assert gate.check(candidate, base, spec)[0] == ["pass_hat_5"]

    candidate["metrics"]["pass_hat_5"] = 1.0
    assert gate.check(candidate, base, spec)[0] == ["integrity"]
