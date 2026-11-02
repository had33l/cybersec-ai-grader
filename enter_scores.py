#!/usr/bin/env python3
"""Type in a friend's PAPER scores (exactly as they wrote them) -> data/labels_NAME.jsonl

  python3 enter_scores.py NAME            start from item 1 (or resume where the file ends)
  python3 enter_scores.py NAME --start 21 start from item #21 of the sheet

Type scores separated by spaces, in sheet order, e.g.:   4 5 3 d 5 4 2
  d       = the rater wrote D (dropped item); you can type  d:unclear_question  (no spaces) to keep a reason
  Press Enter on an empty line when you are finished. Every score is echoed with its item id so you can check it against the paper.
"""
import argparse, json, os
ap = argparse.ArgumentParser()
ap.add_argument("name"); ap.add_argument("--start", type=int, default=0)
ap.add_argument("--items", default="data/to_label.jsonl")
a = ap.parse_args()
items = [json.loads(l) for l in open(a.items)]
out = f"data/labels_{a.name}.jsonl"
done = [json.loads(l) for l in open(out)] if os.path.exists(out) else []
pos = (a.start - 1) if a.start else len(done)
print(f"{len(done)} already saved in {out}. Next item to enter: #{pos + 1} ({items[pos]['id']}).")
while pos < len(items):
    line = input(f"scores from #{pos + 1}: ").strip()
    if not line:
        break
    batch = []
    for tok in line.split():
        if pos + len(batch) >= len(items):
            print("  (more scores than items - ignoring the rest)"); break
        it = items[pos + len(batch)]
        t = tok.lower()
        if t in "12345" and len(t) == 1:
            batch.append({"id": it["id"], "labeller": a.name, "overall": int(t), "reason": ""})
        elif t.startswith("d"):
            batch.append({"id": it["id"], "labeller": a.name, "dropped": True, "drop_reason": tok[2:] if t.startswith("d:") else "dropped on paper"})
        else:
            print(f"  '{tok}' is not 1-5 or d - nothing from this line was saved, retype it"); batch = None; break
    if batch is None:
        continue
    for k, r in enumerate(batch):
        print(f"   #{pos + k + 1:<3} {r['id']:<7} -> " + (f"{r['overall']}" if "overall" in r else "DROP"))
    if input("  correct? [Enter = save, n = retype] ").strip().lower() == "n":
        continue
    with open(out, "a") as f:
        for r in batch:
            f.write(json.dumps(r) + "\n")
    pos += len(batch)
print(f"Saved. {sum(1 for _ in open(out))} rows in {out}.")
