#!/usr/bin/env python3
"""Summarize a results run: overall score, per-criterion, per-category, cost/latency.

Usage: python3 -m harness.report results/run_v1.jsonl
"""
import json
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.schema import CRITERIA


def main():
    if len(sys.argv) < 2:
        print("usage: python3 -m harness.report <results.jsonl>")
        sys.exit(1)
    path = sys.argv[1]
    rows = [json.loads(l) for l in open(path) if l.strip()]

    scored = [r for r in rows if "overall" in r]
    n_total = len(rows)
    n_scored = len(scored)
    n_unsafe = sum(1 for r in scored if r.get("unsafe"))
    n_errors = n_total - n_scored

    print(f"Run: {path}")
    print(f"Items: {n_total}  |  scored: {n_scored}  |  parse/gen failures: {n_errors}")
    if n_scored == 0:
        return

    avg_overall = sum(r["overall"] for r in scored) / n_scored
    print(f"\nAverage overall score: {avg_overall:.2f} / 5")
    print(f"Flagged unsafe: {n_unsafe} ({100*n_unsafe/n_scored:.1f}%)")

    print("\nPer-criterion averages:")
    for c in CRITERIA:
        vals = [r["scores"][c] for r in scored if "scores" in r]
        if vals:
            print(f"  {c:14s} {sum(vals)/len(vals):.2f}")

    print("\nScore distributions (count, %):")
    for name, getter in [("overall", lambda r: r["overall"])] + [(c, (lambda c: lambda r: r["scores"][c])(c)) for c in CRITERIA]:
        vals = [getter(r) for r in scored if "scores" in r]
        cells = "  ".join(f"{k}: {vals.count(k)} ({100*vals.count(k)/len(vals):.1f}%)" for k in range(1, 6))
        print(f"  {name:13s} {cells}")

    print("\nPer-category averages:")
    by_cat = defaultdict(list)
    for r in scored:
        by_cat[r["category"]].append(r["overall"])
    for cat, vals in sorted(by_cat.items()):
        print(f"  {cat:20s} {sum(vals)/len(vals):.2f}  (n={len(vals)})")

    gen_lat = [r["gen_latency_s"] for r in rows if "gen_latency_s" in r]
    judge_lat = [r["judge_latency_s"] for r in rows if "judge_latency_s" in r]
    if gen_lat:
        print(f"\nMedian generation latency: {sorted(gen_lat)[len(gen_lat)//2]:.2f}s")
    if judge_lat:
        print(f"Median judge latency:      {sorted(judge_lat)[len(judge_lat)//2]:.2f}s")


if __name__ == "__main__":
    main()
