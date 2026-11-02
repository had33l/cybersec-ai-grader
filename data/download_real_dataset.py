#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import random
from pathlib import Path
from collections import defaultdict

OUT_DIR = Path(__file__).parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=160, help="how many items to keep, balanced across themes")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    try:
        from datasets import load_dataset
    except ImportError:
        raise SystemExit(
            "Missing the 'datasets' package. Run:\n"
            "  pip install datasets --break-system-packages\n"
            "then re-run this script."
        )

    print("Downloading Rowden/CybersecurityQAA from Hugging Face...")
    ds = load_dataset("Rowden/CybersecurityQAA", split="train")
    print(f"Got {len(ds)} raw entries.")

    random.seed(args.seed)
    by_theme = defaultdict(list)

    for row in ds:
        v = row.get("vars", row)  # some HF parquet conversions flatten 'vars' into top-level columns
        question = v.get("question")
        if not question:
            continue
        theme = (v.get("theme", "General") or "General").strip()
        theme = theme.replace("Articial", "Artificial")  # typo present in the source dataset
        answer = v.get("answer", "")
        rubric_points = []
        asserts = row.get("assert", [])
        for a in asserts:
            val = a.get("value") if isinstance(a, dict) else None
            if val:
                rubric_points.append(val)
        if not rubric_points:
            rubric_points = ["Answer should be technically accurate, relevant, and complete per the reference answer."]

        by_theme[theme].append({
            "category": theme,
            "question": question,
            "must_mention": rubric_points,
            "reference_answer": answer,
            "expert_reviewed": v.get("reviewed_by_expert", "FALSE") == "TRUE",
        })

    print("Themes found:", {k: len(v) for k, v in by_theme.items()})

    # Round-robin across themes until we have --n items. (A fixed per-theme
    # cap loses items whenever a theme has fewer entries than the cap, which
    # is how an earlier version ended up with 134 instead of 160.)
    themes = sorted(by_theme.keys())
    for t in themes:
        random.shuffle(by_theme[t])
    balanced = []
    idx = 0
    while len(balanced) < args.n and any(idx < len(by_theme[t]) for t in themes):
        for t in themes:
            if idx < len(by_theme[t]) and len(balanced) < args.n:
                balanced.append(by_theme[t][idx])
        idx += 1
    random.shuffle(balanced)
    if len(balanced) < args.n:
        print(f"WARNING: only {len(balanced)} items available, fewer than requested {args.n}")

    for i, r in enumerate(balanced, start=1):
        r["id"] = f"CS-{i:03d}"
    # reorder keys nicely
    balanced = [
        {"id": r["id"], "category": r["category"], "question": r["question"],
         "must_mention": r["must_mention"], "reference_answer": r["reference_answer"],
         "expert_reviewed": r["expert_reviewed"]}
        for r in balanced
    ]

    out_path = OUT_DIR / "golden_set.jsonl"
    with out_path.open("w") as f:
        for r in balanced:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Wrote {len(balanced)} items to {out_path}")

    # 60/40 dev/test split, same as before
    random.shuffle(balanced)
    split = int(len(balanced) * 0.6)
    dev, test = balanced[:split], balanced[split:]
    with (OUT_DIR / "dev_set.jsonl").open("w") as f:
        for r in dev:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with (OUT_DIR / "test_set.jsonl").open("w") as f:
        for r in test:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Split: dev={len(dev)}, test={len(test)}")
    notice = OUT_DIR / "PLACEHOLDER_NOTICE.md"
    if notice.exists():
        notice.unlink()
        print("Removed data/PLACEHOLDER_NOTICE.md (real data is now in place).")
    print("\nNow FREEZE it: git add data && git commit -m 'Freeze golden set' - do not re-run this script afterwards,")
    print("it would change the ids and invalidate every result.")
    print("\nSource: Rowden/CybersecurityQAA (MIT license)")
    print("https://huggingface.co/datasets/Rowden/CybersecurityQAA")
    print("Squire, S. & Thornton, I. (2024). Evaluating the Effectiveness of Large Language")
    print("Models as Cybersecurity Advisors. Journal of Cybersecurity Research.")


if __name__ == "__main__":
    main()
