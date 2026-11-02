#!/usr/bin/env python3
"""Prints a ready-to-paste CHANGELOG.md row from a results file (+ delta vs a previous file).
Usage: python3 -m harness.changelog_row v2 results/run_test_v2.jsonl --prev results/run_test_v1.jsonl \
          --files system_prompt_v2.txt --change "why"
"""
import argparse, json, statistics


def stats(p):
    r = [json.loads(l) for l in open(p) if l.strip()]
    sc = [x for x in r if "overall" in x]
    return len(r), len(sc), statistics.mean(x["overall"] for x in sc), sum(bool(x.get("unsafe")) for x in sc)


ap = argparse.ArgumentParser()
ap.add_argument("version"); ap.add_argument("run")
ap.add_argument("--prev"); ap.add_argument("--files", default=""); ap.add_argument("--change", default="")
a = ap.parse_args()
n, ns, m, u = stats(a.run)
d = "-"
if a.prev:
    d = f"{m - stats(a.prev)[2]:+.2f}"
print(f"| {a.version} | {a.files} | {a.change} | {m:.2f} / 5 (n={ns}/{n} scored, {u} unsafe) | {d} |")
