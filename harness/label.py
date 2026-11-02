#!/usr/bin/env python3
"""
Terminal labelling tool. Shows one item at a time and saves after every item,
so you can quit (q) and resume later — already-labelled ids are skipped.

  python3 harness/label.py --in data/to_label.jsonl --out data/labels_hadeel.jsonl --labeller hadeel

Each labeller runs this on their own machine/copy and never sees the other's
scores or the judge's scores. Score 1-5 following data/labelling_guide.md.
Type d to DROP an unusable item (you'll be asked why); drops are counted and
reported by harness/finalize.py.
Add --criteria to also score the five criteria (slower); 'overall' is what
the agreement script uses.
"""
import argparse
import json
import os
import textwrap

CRITERIA = ["accuracy", "relevance", "clarity", "completeness", "safety"]


def ask_int(prompt):
    while True:
        s = input(prompt).strip().lower()
        if s in ("q", "quit"):
            return None
        if s in ("d", "drop"):
            return "drop"
        if s in ("1", "2", "3", "4", "5"):
            return int(s)
        print("  enter 1-5, d to drop this item, or q to quit")


def wrap(label, text):
    print(f"\n{label}")
    for line in str(text).splitlines() or [""]:
        print(textwrap.fill(line, 100, initial_indent="  ", subsequent_indent="  "))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--labeller", required=True)
    ap.add_argument("--criteria", action="store_true", help="also score the 5 criteria")
    ap.add_argument("--hide-reference", action="store_true", help="don't show the reference answer")
    args = ap.parse_args()

    items = [json.loads(l) for l in open(args.inp) if l.strip()]
    done = set()
    if os.path.exists(args.out):
        done = {json.loads(l)["id"] for l in open(args.out) if l.strip()}
    todo = [it for it in items if it["id"] not in done]
    print(f"{len(done)} already labelled, {len(todo)} to go. Type q at any score prompt to stop.\n")

    for n, it in enumerate(todo, 1):
        print("=" * 100)
        print(f"[{len(done) + n}/{len(items)}]  {it['id']}  ({it['category']})")
        wrap("QUESTION:", it["question"])
        if it.get("reference_answer") and not args.hide_reference:
            wrap("REFERENCE (expert) ANSWER:", it["reference_answer"])
        if it.get("must_mention"):
            wrap("RUBRIC:", " | ".join(it["must_mention"]))
        wrap("ANSWER TO SCORE:", it["answer"])
        print()

        row = {"id": it["id"], "labeller": args.labeller}
        dropped = False
        if args.criteria:
            scores = {}
            for c in CRITERIA:
                v = ask_int(f"  {c:13s} 1-5 (d = drop item): ")
                if v is None:
                    return
                if v == "drop":
                    dropped = True
                    break
                scores[c] = v
            row["scores"] = scores
        overall = "drop" if dropped else ask_int("  OVERALL       1-5 (d = drop item): ")
        if overall == "drop":
            row.pop("scores", None)
            row["dropped"] = True
            row["drop_reason"] = input("  why drop? (e.g. ambiguous question, broken answer): ").strip()
            with open(args.out, "a") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            continue
        if overall is None:
            print("Stopped. Run the same command again to resume.")
            return
        row["overall"] = overall
        row["reason"] = input("  reason (optional, Enter to skip): ").strip()

        with open(args.out, "a") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"\nAll done. Labels saved to {args.out}")


if __name__ == "__main__":
    main()
