#!/usr/bin/env python3
"""
Builds the file the human labellers score. Judge scores are deliberately NOT
included, so labellers stay blind to the judge.

Usage (label everything you have answers for):
  python3 harness/sample_for_labelling.py --run results/run_dev.jsonl results/run_test.jsonl \\
      --out data/to_label.jsonl
Use --n 40 for a random subset instead of all rows.
"""
import argparse
import json
import random


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", nargs="+", required=True, help="one or more results jsonl files")
    ap.add_argument("--dataset", default="data/golden_set.jsonl", help="adds reference_answer + must_mention")
    ap.add_argument("--n", type=int, default=0, help="0 = all rows")
    ap.add_argument("--out", default="data/to_label.jsonl")
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()

    data = {json.loads(l)["id"]: json.loads(l) for l in open(args.dataset) if l.strip()}
    rows = []
    for path in args.run:
        rows += [r for r in (json.loads(l) for l in open(path) if l.strip()) if "answer" in r]

    seen, uniq = set(), []
    for r in rows:
        if r["id"] not in seen:
            seen.add(r["id"])
            uniq.append(r)
    random.seed(args.seed)
    random.shuffle(uniq)
    if args.n:
        uniq = uniq[: args.n]

    with open(args.out, "w") as f:
        for r in uniq:
            d = data.get(r["id"], {})
            f.write(json.dumps({
                "id": r["id"], "category": r["category"], "question": r["question"],
                "answer": r["answer"],
                "reference_answer": d.get("reference_answer", ""),
                "must_mention": d.get("must_mention", []),
            }, ensure_ascii=False) + "\n")
    print(f"Wrote {len(uniq)} items to {args.out}")


if __name__ == "__main__":
    main()
