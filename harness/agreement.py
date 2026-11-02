#!/usr/bin/env python3
"""
Computes agreement between two human labellers, and between humans and the
judge, on the 'overall' score.

Reports:
  - exact match rate
  - within-1-point agreement rate
  - Cohen's kappa (treats 1-5 as categorical labels)

Usage:
  python3 -m harness.agreement --a data/labels_alice.jsonl --b data/labels_bob.jsonl
  python3 -m harness.agreement --a data/labels_alice.jsonl --b results/run_v1.jsonl --b-field overall
"""
import argparse
import json
from collections import Counter


def read_scores(path, field="overall"):
    scores = {}
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if field in r:
            scores[r["id"]] = r[field]
    return scores


def cohens_kappa(pairs):
    """pairs: list of (a, b) integer labels 1-5."""
    n = len(pairs)
    if n == 0:
        return None
    po = sum(1 for a, b in pairs if a == b) / n

    a_counts = Counter(a for a, _ in pairs)
    b_counts = Counter(b for _, b in pairs)
    pe = sum((a_counts[k] / n) * (b_counts[k] / n) for k in set(a_counts) | set(b_counts))

    if pe == 1:
        return 1.0
    return (po - pe) / (1 - pe)


def compare(scores_a, scores_b, label_a="A", label_b="B"):
    common_ids = sorted(set(scores_a) & set(scores_b))
    pairs = [(scores_a[i], scores_b[i]) for i in common_ids]
    n = len(pairs)
    if n == 0:
        print(f"No overlapping item IDs between {label_a} and {label_b}.")
        return

    exact = sum(1 for a, b in pairs if a == b) / n
    within1 = sum(1 for a, b in pairs if abs(a - b) <= 1) / n
    kappa = cohens_kappa(pairs)

    print(f"\n{label_a} vs {label_b}  (n={n} shared items)")
    print(f"  Exact match:      {exact*100:.1f}%")
    print(f"  Within 1 point:   {within1*100:.1f}%")
    print(f"  Cohen's kappa:    {kappa:.3f}" if kappa is not None else "  Cohen's kappa: n/a")

    diffs = sorted(((abs(a - b), i) for i, (a, b) in zip(common_ids, pairs)), reverse=True)
    big_diffs = [i for d, i in diffs if d >= 2]
    if big_diffs:
        print(f"  Items differing by 2+: {len(big_diffs)} -> {big_diffs[:10]}{' ...' if len(big_diffs) > 10 else ''}")
        print("  (review these per the labelling guide's disagreement process)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--a-field", default="overall")
    ap.add_argument("--b-field", default="overall")
    args = ap.parse_args()

    scores_a = read_scores(args.a, args.a_field)
    scores_b = read_scores(args.b, args.b_field)
    compare(scores_a, scores_b, args.a, args.b)


if __name__ == "__main__":
    main()
