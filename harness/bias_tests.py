#!/usr/bin/env python3
"""
Reliability tests for the judge itself.

1. Position bias: for each question we compare TWO answers to that same
   question — the system's answer and the dataset's expert reference answer
   — twice, once in each order. If the judge prefers a different *answer*
   just because the slots were swapped, that's a position flip.

2. Verbosity bias: take answers the judge already scored, pad them with
   filler that adds no information, re-score with the same rubric and the
   same must_mention, and see if the grade goes up.

Usage:
  python3 harness/bias_tests.py --run results/run_v1.jsonl \\
      --dataset data/golden_set.jsonl --judge-model llama3.1:8b \\
      --out results/bias_report.json
  Add --mock to test without a real LLM.
"""
from __future__ import annotations
import argparse
import json
import random
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.llm_client import LLMClient, LLMError
from harness.system_under_test import load_prompt
from harness.judge import judge_answer, judge_pairwise
from harness.runner import MockClient

FILLER = (
    " It's also worth remembering that cybersecurity is an ongoing process, not a "
    "one-time fix, so staying informed and cautious over time really does make a "
    "meaningful difference to your overall security posture."
)


def make_robust(client, tries=4):  # BIAS-RETRY-PATCH
    orig = client.chat

    def chat(*a, **k):
        for i in range(tries):
            try:
                return orig(*a, **k)
            except (LLMError, requests.exceptions.RequestException) as e:
                if i == tries - 1:
                    raise LLMError(f"{type(e).__name__}: {e}") from e
                wait = 30 * (i + 1)
                print(f"    LLM error ({str(e)[:80]}) - retry {i + 1}/{tries - 1} in {wait}s", flush=True)
                time.sleep(wait)
    client.chat = chat
    return client


def load_dataset(path):
    return {json.loads(l)["id"]: json.loads(l) for l in open(path) if l.strip()}


def position_bias_test(client, rows, data, n_pairs=30, seed=0):
    random.seed(seed)
    usable = [r for r in rows if r.get("answer") and data.get(r["id"], {}).get("reference_answer")]
    if not usable:
        return {"pairs_tested": 0, "note": "no rows with both a model answer and a reference_answer"}
    sample = random.sample(usable, min(n_pairs, len(usable)))

    consistent = flipped = ties_both = skipped = 0
    picked_first_slot = total_calls = 0
    details = []
    to_name = {"A": None, "B": None}
    for r in sample:
        model_ans = r["answer"]
        ref_ans = data[r["id"]]["reference_answer"]
        # order 1: A=model, B=reference ; order 2: A=reference, B=model
        try:
            w1, _, ok1 = judge_pairwise(client, r["question"], model_ans, ref_ans)
            w2, _, ok2 = judge_pairwise(client, r["question"], ref_ans, model_ans)
        except LLMError as e:
            print(f"  position: skipping {r['id']} after retries ({str(e)[:80]})", flush=True)
            skipped += 1
            continue
        print(f"  position {len(details) + skipped + 1}/{len(sample)} done", flush=True)
        if not (ok1 and ok2):
            skipped += 1
            continue
        v1 = {"A": "model", "B": "reference", "TIE": "tie"}[w1]
        v2 = {"A": "reference", "B": "model", "TIE": "tie"}[w2]
        total_calls += 2
        picked_first_slot += (w1 == "A") + (w2 == "A")
        same = v1 == v2
        consistent += same
        flipped += (not same)
        ties_both += (same and v1 == "tie")
        details.append({"id": r["id"], "order1_winner": v1, "order2_winner": v2, "consistent": same})

    tested = len(details)
    return {
        "pairs_tested": tested,
        "consistent": consistent,
        "flipped": flipped,
        "flip_rate": round(flipped / tested, 3) if tested else None,
        "tie_in_both_orders": ties_both,
        "picked_first_slot": picked_first_slot,
        "total_verdicts": total_calls,
        "first_slot_rate": round(picked_first_slot / total_calls, 3) if total_calls else None,
        "skipped_unparseable": skipped,
        "details": details,
    }


def verbosity_bias_test(client, judge_prompt, rows, data, n_items=30, seed=0):
    random.seed(seed)
    scored = [r for r in rows if "overall" in r and r.get("answer")]
    sample = random.sample(scored, min(n_items, len(scored)))

    raised = unchanged = dropped = 0
    details = []
    for r in sample:
        must = data.get(r["id"], {}).get("must_mention", [])
        try:
            result, _, ok, _ = judge_answer(client, judge_prompt, r["question"], must, r["answer"] + FILLER)
        except LLMError as e:
            print(f"  verbosity: skipping {r['id']} after retries ({str(e)[:80]})", flush=True)
            continue
        if not ok:
            continue
        print(f"  verbosity {len(details) + 1}/{len(sample)} done", flush=True)
        delta = result["overall"] - r["overall"]
        raised += delta > 0
        dropped += delta < 0
        unchanged += delta == 0
        details.append({"id": r["id"], "original_score": r["overall"],
                        "padded_score": result["overall"], "delta": delta})

    tested = len(details)
    return {
        "items_tested": tested,
        "score_rose": raised,
        "score_unchanged": unchanged,
        "score_dropped": dropped,
        "score_rose_rate": round(raised / tested, 3) if tested else None,
        "details": details,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="a results jsonl from harness/runner.py")
    ap.add_argument("--dataset", default="data/golden_set.jsonl", help="for reference answers + must_mention")
    ap.add_argument("--judge-prompt", default="prompts/judge_prompt_v1.txt")
    ap.add_argument("--out", default="results/bias_report.json")
    ap.add_argument("--judge-backend", default=None)
    ap.add_argument("--judge-model", default=None)
    ap.add_argument("--n", type=int, default=30, help="items per test")
    ap.add_argument("--mock", action="store_true")
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(args.run) if l.strip()]
    data = load_dataset(args.dataset)
    judge_prompt = load_prompt(args.judge_prompt)
    client = MockClient() if args.mock else LLMClient(backend=args.judge_backend, model=args.judge_model)
    make_robust(client)

    print("Running position bias test (model answer vs expert reference, both orders)...")
    pos = position_bias_test(client, rows, data, n_pairs=args.n)
    if pos["pairs_tested"]:
        print(f"  {pos['pairs_tested']} pairs: {pos['consistent']} consistent, "
              f"{pos['flipped']} flipped ({pos['flip_rate']*100:.1f}%); "
              f"picked the first slot in {pos['picked_first_slot']}/{pos['total_verdicts']} verdicts")
    else:
        print("  0 pairs tested:", pos.get("note", "all verdicts unparseable"))

    print("Running verbosity bias test...")
    verb = verbosity_bias_test(client, judge_prompt, rows, data, n_items=args.n)
    if verb["items_tested"]:
        print(f"  {verb['items_tested']} items: rose {verb['score_rose']}, "
              f"unchanged {verb['score_unchanged']}, dropped {verb['score_dropped']}")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as f:
        json.dump({"position_bias": pos, "verbosity_bias": verb}, f, indent=2)
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
