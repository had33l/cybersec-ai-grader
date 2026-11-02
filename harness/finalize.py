#!/usr/bin/env python3
"""Collects EVERY number the report needs into results/summary.json (+ results/dropped_items.md).

It only reports what exists. Anything not yet measured (no labels, no bias run...)
is written as null and the report prints it as NOT YET MEASURED - nothing is invented.

Usage:
  python3 -m harness.finalize --runs results/run_dev_v1.jsonl results/run_test_v1.jsonl \
      --labels data/labels_alice.jsonl data/labels_bob.jsonl
"""
from __future__ import annotations
import argparse, json, re, statistics, sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.agreement import cohens_kappa
from harness.cost import cost_model
from harness.schema import CRITERIA


def jl(path):
    return [json.loads(l) for l in open(path) if l.strip()] if Path(path).exists() else []


def agree(pairs):
    n = len(pairs)
    if not n:
        return None
    return {"n": n,
            "exact": sum(a == b for a, b in pairs), "exact_pct": round(100 * sum(a == b for a, b in pairs) / n, 1),
            "within1": sum(abs(a - b) <= 1 for a, b in pairs),
            "within1_pct": round(100 * sum(abs(a - b) <= 1 for a, b in pairs) / n, 1),
            "kappa": round(cohens_kappa(pairs), 3),
            "mean_signed_diff_a_minus_b": round(statistics.mean(a - b for a, b in pairs), 2)}


def run_summary(rows):
    sc = [r for r in rows if "overall" in r]
    if not rows:
        return None
    out = {"items": len(rows), "scored": len(sc), "failures": len(rows) - len(sc)}
    if sc:
        o = [r["overall"] for r in sc]
        out.update({"mean_overall": round(statistics.mean(o), 3),
                    "overall_counts": {k: o.count(k) for k in range(1, 6)},
                    "overall_pct": {k: round(100 * o.count(k) / len(o), 1) for k in range(1, 6)},
                    "unsafe": sum(bool(r.get("unsafe")) for r in sc),
                    "per_criterion": {c: round(statistics.mean(r["scores"][c] for r in sc), 2) for c in CRITERIA}})
    return out


def dataset_check(rows, golden):
    mism = [r["id"] for r in rows if r["id"] not in golden or golden[r["id"]]["question"] != r["question"]]
    return {"rows": len(rows), "mismatched_vs_golden_set": len(mism), "examples": mism[:8]}


def parse_changelog(path):
    out = []
    if not Path(path).exists():
        return out
    for line in open(path):
        if line.startswith("| v") and "---" not in line:
            out.append([c.strip() for c in line.strip().strip("|").split("|")])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="*", default=[], help="judged results files (dev and test)")
    ap.add_argument("--test-run", help="the test-set run used for the headline score + cost")
    ap.add_argument("--labels", nargs="*", default=[], help="two (or more) label files")
    ap.add_argument("--golden", default="data/golden_set.jsonl")
    ap.add_argument("--bias", default="results/bias_report.json")
    ap.add_argument("--changelog", default="prompts/CHANGELOG.md")
    ap.add_argument("--assumptions", default="cost_assumptions.json")
    ap.add_argument("--out", default="results/summary.json")
    a = ap.parse_args()

    golden = {r["id"]: r for r in jl(a.golden)}
    summary = {"golden_set_size": len(golden)}

    # ---- runs + dataset consistency ----
    all_rows = {}
    summary["runs"], summary["dataset_consistency"] = {}, {}
    for p in a.runs:
        rows = jl(p)
        summary["runs"][p] = run_summary(rows)
        summary["dataset_consistency"][p] = dataset_check(rows, golden)
        for r in rows:
            if "overall" in r:
                all_rows.setdefault(r["id"], r)

    # ---- labels ----
    labs = {}
    for p in a.labels:
        rows = jl(p)
        if rows:
            labs[rows[0]["labeller"]] = {r["id"]: r for r in rows}
    summary["labels"] = None
    consensus = {}
    if len(labs) >= 2:
        (na, A), (nb, B) = list(labs.items())[:2]
        both = sorted(set(A) & set(B))
        dropped = {i: (A.get(i, {}).get("drop_reason") or B.get(i, {}).get("drop_reason") or "") for i in both
                   if A[i].get("dropped") or B[i].get("dropped")}
        usable = [i for i in both if "overall" in A[i] and "overall" in B[i]]
        pairs = [(A[i]["overall"], B[i]["overall"]) for i in usable]
        big = [i for i in usable if abs(A[i]["overall"] - B[i]["overall"]) >= 2]
        for i in usable:
            if i not in big:
                consensus[i] = (A[i]["overall"] + B[i]["overall"]) / 2
        summary["labels"] = {
            "labellers": [na, nb], "labelled_by_a": len(A), "labelled_by_b": len(B), "labelled_by_both": len(both),
            "dropped_by_either": len(dropped), "human_human": agree(pairs),
            "disagreements_2plus": len(big), "disagreement_ids": big,
            "consensus_items": len(consensus)}
        with open("results/dropped_items.md", "w") as f:
            f.write("# Dropped and disputed items\n\n## Dropped by a labeller\n\n")
            f.write("\n".join(f"- {i}: {why or '(no reason given)'}" for i, why in dropped.items()) or "_none_")
            f.write("\n\n## Labellers differed by 2+ points (discuss, then re-label or drop)\n\n")
            f.write("\n".join(f"- {i}: {na}={A[i]['overall']} vs {nb}={B[i]['overall']}" for i in big) or "_none_")
            f.write("\n")
        # judge vs humans (blind judge scores come from the runs)
        jr = {}
        for lab, L in ((na, A), (nb, B)):
            pr = [(all_rows[i]["overall"], L[i]["overall"]) for i in L if "overall" in L[i] and i in all_rows]
            jr[f"judge_vs_{lab}"] = agree(pr)
        pc = [(all_rows[i]["overall"], round(v + 1e-9)) for i, v in consensus.items() if i in all_rows]
        jr["judge_vs_consensus(rounded mean)"] = agree(pc)
        conf = Counter((round(v + 1e-9), all_rows[i]["overall"]) for i, v in consensus.items() if i in all_rows)
        jr["confusion_human_consensus_vs_judge"] = {f"human={h},judge={j}": n for (h, j), n in sorted(conf.items())}
        summary["judge_vs_human"] = jr
        with open("data/labels_consensus.jsonl", "w") as f:
            for i, v in consensus.items():
                f.write(json.dumps({"id": i, "labeller": "consensus", "overall": round(v + 1e-9), "mean": v}) + "\n")
    else:
        summary["judge_vs_human"] = None

    # ---- bias ----
    summary["bias"] = json.load(open(a.bias)) if Path(a.bias).exists() else None
    if summary["bias"]:  # keep summary small
        for k in ("position_bias", "verbosity_bias"):
            summary["bias"][k].pop("details", None)

    # ---- cost + headline ----
    summary["headline_test_run"] = a.test_run
    if a.test_run and Path(a.test_run).exists():
        summary["cost"] = cost_model(jl(a.test_run), json.load(open(a.assumptions)))
        meta = Path(a.test_run + ".meta.json")
        summary["test_run_meta"] = json.load(open(meta)) if meta.exists() else None
    else:
        summary["cost"], summary["test_run_meta"] = None, None
    summary["changelog"] = parse_changelog(a.changelog)

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(summary, open(a.out, "w"), indent=2)
    print(f"Wrote {a.out}")
    bad = {p: d for p, d in summary["dataset_consistency"].items() if d["mismatched_vs_golden_set"]}
    if bad:
        print("\nWARNING - these runs do not match data/golden_set.jsonl (same id, different question):")
        for p, d in bad.items():
            print(f"  {p}: {d['mismatched_vs_golden_set']}/{d['rows']} rows mismatch, e.g. {d['examples']}")
    if summary["labels"] is None:
        print("NOT YET MEASURED: human labels (need two label files).")
    if summary["bias"] is None:
        print("NOT YET MEASURED: judge bias (run harness/bias_tests.py).")


if __name__ == "__main__":
    main()
