"""Statistics students implement (M2 judge calibration, M4 paired bootstrap).

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
Reference values to self-check are in tests/test_lab9_stats.py.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import comb
from numbers import Integral

import numpy as np
from scipy.stats import bootstrap

POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """tp/fp/fn/tn with FAIL as positive."""
    counts = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    keys = {("FAIL", "FAIL"): "tp", ("PASS", "FAIL"): "fp",
            ("FAIL", "PASS"): "fn", ("PASS", "PASS"): "tn"}
    for expected, predicted in zip(human, judge, strict=True):
        try:
            counts[keys[expected, predicted]] += 1
        except KeyError:
            raise ValueError("judge and human labels must be PASS or FAIL") from None
    return counts


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    m = confusion(human, judge)
    n_predicted, n_actual = m["tp"] + m["fp"], m["tp"] + m["fn"]
    return (m["tp"] / n_predicted if n_predicted else 0.0,
            m["tp"] / n_actual if n_actual else 0.0)


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e). Raise ValueError when undefined (p_e == 1):
    a constant judge has no signal and must FAIL calibration, not pass on a technicality."""
    m = confusion(human, judge)
    tp, fp, fn, tn = (m[key] for key in ("tp", "fp", "fn", "tn"))
    n = tp + fp + fn + tn
    chance_agreements = (tp + fn) * (tp + fp) + (tn + fp) * (tn + fn)
    if chance_agreements == n * n:
        raise ValueError("Cohen's kappa is undefined")
    return ((tp + tn) * n - chance_agreements) / (n * n - chance_agreements)


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct an observed failure rate for judge error; clip to [0, 1]."""
    youden_j = sensitivity + specificity - 1
    if youden_j == 0:
        raise ValueError("failure rate is not identifiable when sensitivity + specificity is 1")
    estimate = (observed_rate + specificity - 1) / youden_j
    return float(np.clip(estimate, 0.0, 1.0))


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """a[i], b[i] = per-item mean over seeds, SAME items, SAME order.
    Return (mean(a)-mean(b), lo, hi) with scipy.stats.bootstrap(paired=True, method="percentile",
    rng=numpy.random.default_rng(rng)). If a == b everywhere return (0.0, 0.0, 0.0)."""
    pr, base = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if pr.ndim != 1 or pr.shape != base.shape or not pr.size:
        raise ValueError("bootstrap requires nonempty one-dimensional paired samples")
    if not (np.isfinite(pr).all() and np.isfinite(base).all()):
        raise ValueError("bootstrap samples must be finite")
    delta = pr - base
    estimate = float(delta.mean())
    if np.all(delta == delta[0]):
        return estimate, estimate, estimate

    def mean_difference(candidate, reference, axis):
        return np.mean(candidate - reference, axis=axis)

    interval = bootstrap(
        (pr, base), mean_difference, paired=True, method="percentile",
        n_resamples=n_resamples, confidence_level=confidence, rng=np.random.default_rng(rng),
    ).confidence_interval
    return estimate, float(interval.low), float(interval.high)


def _validate_trials(n: int, c: int, k: int) -> None:
    if (any(isinstance(value, bool) or not isinstance(value, Integral) for value in (n, c, k))
            or not (1 <= k <= n and 0 <= c <= n)):
        raise ValueError("expected integer trial counts with 1 <= k <= n and 0 <= c <= n")


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that AT LEAST ONE of k trials drawn from n (c of them passing) passes.
    Unbiased estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k). Raise ValueError if k > n."""
    _validate_trials(n, c, k)
    total = comb(n, k)
    return (total - comb(n - c, k)) / total


def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k (tau-bench, Yao et al. 2024): probability that ALL k trials drawn from n pass.
    Unbiased estimator: C(c, k) / C(n, k). Raise ValueError if k > n.
    pass^k <= pass@1 <= pass@k; a reliable agent keeps pass^k close to pass@1."""
    _validate_trials(n, c, k)
    return comb(c, k) / comb(n, k)
