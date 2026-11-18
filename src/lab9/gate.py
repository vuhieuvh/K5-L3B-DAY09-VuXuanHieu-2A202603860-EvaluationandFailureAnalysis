"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from itertools import product
from numbers import Real
from pathlib import Path
from statistics import mean

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item, stability_metrics
from lab9.graders import GRADERS


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - a reported stability metric that disagrees with the per-item trial grades
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems = []
    required = {m["id"] for m in spec["metrics"] if m["id"] in GRADERS or m.get("grader") == "code"}
    declared = {m["id"] for m in spec["metrics"]}
    k_values = set(spec.get("pass_k", []))
    stability_ids = declared & {"pass_5"}
    stability_ids.update(f"{prefix}_{k}" for prefix in ("pass_at", "pass_hat") for k in k_values)
    for metric in declared:
        prefix, _, k = metric.rpartition("_")
        if prefix in {"pass_at", "pass_hat"} and k.isascii() and k.isdecimal() and int(k) > 0:
            k_values.add(int(k))
            stability_ids.add(f"{prefix}_{int(k)}")
    tags_by_report = {}
    for name, report in (("PR", pr), ("baseline", base)):
        manifest, rows = report["manifest"], report["rows"]
        pairs = [(row.get("item_id"), row.get("seed")) for row in rows]
        pair_set = set(pairs)
        items = {item for item, _ in pairs}
        seeds = manifest["seeds"]
        if (None in items or None in seeds or not items or not seeds
                or len(items) != manifest["items"] or len(seeds) != len(set(seeds))
                or len(rows) != manifest["items"] * len(seeds)
                or len(pair_set) != len(pairs) or pair_set != set(product(items, seeds))):
            problems.append(f"{name} rows do not form a complete, unique item × seed grid")
        if report.get("evaluator_failures"):
            problems.append(f"{name} has evaluator_failures")
        for metric, value in report["metrics"].items():
            if value is not None and (not isinstance(value, Real) or not math.isfinite(value)):
                problems.append(f"{name} metric {metric} is not finite numeric data")
        invalid = {metric for metric in required for row in rows
                   if type(row.get(metric)) is not bool}
        if invalid:
            problems.append(f"{name} has missing or invalid row grades: {', '.join(sorted(invalid))}")
        for metric in sorted(required - invalid):
            if not rows:
                continue
            values = [row[metric] for row in rows]
            expected = sum(values) if metric in {"approval_bypass", "secret_leak"} else mean(values)
            value = report["metrics"].get(metric)
            if not isinstance(value, Real) or not math.isclose(value, expected, abs_tol=0.00005):
                problems.append(f"{name} metric {metric} disagrees with its row grades")
        if stability_ids and rows:
            if any(type(row.get("pass_rate")) is not bool for row in rows):
                problems.append(f"{name} stability metrics need a valid pass_rate grade for every row")
            else:
                recomputed = stability_metrics(rows, sorted(k_values))
                for metric in sorted(stability_ids):
                    value = report["metrics"].get(metric)
                    if isinstance(value, bool) or value != recomputed[metric]:
                        problems.append(f"{name} metric {metric} disagrees with its row grades")
        tags_by_report[name] = {pair: frozenset(row.get("slices") or ())
                                for pair, row in zip(pairs, rows, strict=True)}
    pr_tags, base_tags = tags_by_report["PR"], tags_by_report["baseline"]
    if pr_tags.keys() != base_tags.keys():
        problems.append("PR item × seed pairs differ from baseline")
    elif pr_tags != base_tags:
        problems.append("PR slice tags differ from baseline")
    if pr["manifest"].get("labels_sha") != base["manifest"].get("labels_sha"):
        problems.append("PR labels SHA differs from baseline")
    if base_spec is not None and spec.get("eval_set_version") == base_spec.get("eval_set_version"):
        problems.extend(_ratchet(spec, base_spec))
    return problems


def _ratchet(spec: dict, base_spec: dict) -> list[str]:
    problems = []
    for group in ("metrics", "slices"):
        def key(entry):
            return entry["id"] if group == "metrics" else (entry["name"], entry["metric"])

        current = {key(entry): entry for entry in spec.get(group, [])}
        for original in base_spec.get(group, []):
            name = key(original)
            candidate = current.get(name)
            if candidate is None:
                problems.append(f"ratchet: removed {group} entry {name}")
                continue
            before = original.get("threshold", {}) if group == "metrics" else original
            after = candidate.get("threshold", {}) if group == "metrics" else candidate
            weaker = (
                ("min" in before and ("min" not in after or after["min"] < before["min"]))
                or any(field in before and (field not in after or after[field] > before[field])
                       for field in ("max", "max_increase"))
                or (before.get("no_significant_drop") and not after.get("no_significant_drop"))
                or (original.get("blocking") and not candidate.get("blocking"))
            )
            if weaker:
                problems.append(f"ratchet: loosened {group} entry {name}")
    return problems


def _paired_interval(pr: dict[str, float], base: dict[str, float], spec: dict) -> tuple[float, float, float]:
    keys = sorted(pr)
    settings = spec.get("bootstrap", {})
    return stats.paired_bootstrap(
        [pr[k] for k in keys], [base[k] for k in keys],
        n_resamples=settings.get("n_resamples", 1000),
        rng=settings.get("rng", 2027), confidence=settings.get("confidence", 0.95),
    )


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked, lines = [], []
    for rule in spec.get("slices", []):
        name, metric = rule["name"], rule["metric"]
        label = f"slice:{name}/{metric}"
        a, b = per_item(pr, metric, name), per_item(base, metric, name)
        value = mean(a.values()) if a else None
        note = ""
        failed = value is None or a.keys() != b.keys()
        if failed:
            note = "missing paired slice data"
        else:
            failed = "min" in rule and value < rule["min"]
            if rule.get("no_significant_drop"):
                delta, lo, hi = _paired_interval(a, b, spec)
                note = f"Δ {delta:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                failed = failed or hi < 0
        action = "BLOCK" if rule.get("blocking") else "warn"
        if failed and rule.get("blocking"):
            blocked.append(label)
        lines.append(f"  {label} {value!s} {note} {action if failed else 'ok'}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            if not a or a.keys() != b.keys():
                verdict, note = "missing", "missing paired metric data"
            else:
                d, lo, hi = _paired_interval(a, b, spec)
                note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                if hi < 0:
                    verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
