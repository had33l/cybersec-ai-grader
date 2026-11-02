#!/usr/bin/env python3
"""
Main harness entry point. Runs the system-under-test on every item in a
dataset, judges every answer, and writes one JSON row per item to --out.

Usage:
  python3 -m harness.runner \\
      --dataset data/test_set.jsonl \\
      --system-prompt prompts/system_prompt_v1.txt \\
      --judge-prompt prompts/judge_prompt_v1.txt \\
      --out results/run_v1.jsonl \\
      --backend ollama --model qwen2.5:7b

Add --mock to run without a real LLM (uses a canned fake response) — useful
to verify the pipeline, dataset, and schema logic work before you have
Ollama running.
"""
from __future__ import annotations
import argparse
import requests
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.llm_client import LLMClient, LLMError
from harness.system_under_test import load_prompt, generate_answer
from harness.judge import judge_answer


class MockClient:
    """Stands in for LLMClient when --mock is passed. Lets you smoke-test
    the whole harness without Ollama installed."""
    backend = "mock"
    model = "mock"
    tokens_in = 0
    tokens_out = 0

    def chat(self, system, user, json_mode=False, temperature=0.2):
        from harness.llm_client import LLMResponse
        import random
        time.sleep(0.01)
        self.tokens_in += (len(system.split()) + len(user.split())) * 4 // 3
        if json_mode and "winner" in user:
            text = json.dumps({
                "winner": random.choice(["A", "B", "tie"]),
                "reason": "Mock pairwise verdict for pipeline testing.",
            })
        elif json_mode:
            text = json.dumps({
                "scores": {"accuracy": random.randint(3, 5), "relevance": random.randint(3, 5),
                           "clarity": random.randint(3, 5), "completeness": random.randint(2, 5),
                           "safety": random.randint(4, 5)},
                "overall": random.randint(3, 5),
                "reason": "Mock judge output for pipeline testing.",
                "unsafe": False,
            })
        else:
            text = "This is a mock answer generated without a real LLM, for pipeline testing only."
        self.tokens_out += len(text.split()) * 4 // 3
        return LLMResponse(text=text, latency_s=0.01, raw={})


def _retry(fn, label, tries=4):  # RETRY-PATCH
    for k in range(tries):
        try:
            return fn()
        except (LLMError, requests.exceptions.RequestException) as e:  # TIMEOUT-PATCH
            if k == tries - 1:
                raise LLMError(f"{type(e).__name__}: {e}") from e
            wait = 30 * (k + 1)
            print(f"  {label}: LLM error ({str(e)[:90]}) - retry {k + 1}/{tries - 1} in {wait}s", flush=True)
            time.sleep(wait)


def read_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="data/test_set.jsonl")
    ap.add_argument("--system-prompt", default="prompts/system_prompt_v1.txt")
    ap.add_argument("--judge-prompt", default="prompts/judge_prompt_v1.txt")
    ap.add_argument("--out", default="results/run.jsonl")

    # The answering LLM and the judging LLM are two separate clients, so you
    # can (and should) point them at different models — e.g. a small/fast
    # model answers, a stronger model judges. This also avoids the judge
    # being biased toward its own phrasing if it graded itself.
    ap.add_argument("--answer-backend", default=None, help="ollama | openai (default: env LLM_BACKEND or ollama)")
    ap.add_argument("--answer-model", default=None, help="model that GENERATES answers, e.g. qwen2.5:7b")
    ap.add_argument("--judge-backend", default=None, help="ollama | openai (defaults to --answer-backend)")
    ap.add_argument("--judge-model", default=None, help="model that GRADES answers, e.g. llama3.1:8b (defaults to --answer-model)")

    ap.add_argument("--limit", type=int, default=None, help="only run the first N items")
    ap.add_argument("--mock", action="store_true", help="use two fake LLMs, no network calls")
    args = ap.parse_args()

    items = read_jsonl(args.dataset)
    if args.limit:
        items = items[: args.limit]

    system_prompt = load_prompt(args.system_prompt)
    judge_prompt = load_prompt(args.judge_prompt)

    if args.mock:
        answer_client = MockClient()
        judge_client = MockClient()
    else:
        answer_client = LLMClient(backend=args.answer_backend, model=args.answer_model)
        # judge defaults to the same backend/model as the answerer only if
        # neither judge flag was given; otherwise it's fully independent.
        judge_backend = args.judge_backend or args.answer_backend
        judge_model = args.judge_model or args.answer_model
        judge_client = LLMClient(backend=judge_backend, model=judge_model)

    print(f"Answering with: {'mock' if args.mock else f'{answer_client.backend}/{answer_client.model}'}")
    print(f"Judging with:   {'mock' if args.mock else f'{judge_client.backend}/{judge_client.model}'}\n")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    n_ok, n_parse_fail, n_llm_error = 0, 0, 0
    results = []
    # RESUME-PATCH: rows are appended to --out as they finish; rerunning the same command skips finished items.
    done_ids = set()
    if Path(args.out).exists():
        for line in open(args.out):
            if line.strip():
                r0 = json.loads(line)
                if "overall" in r0 and r0["id"] not in done_ids:
                    results.append(r0); done_ids.add(r0["id"]); n_ok += 1
        with open(args.out, "w") as f:
            for r0 in results:
                f.write(json.dumps(r0, ensure_ascii=False) + "\n")
        if done_ids:
            print(f"Resuming: {len(done_ids)} items already done in {args.out}, skipping them.\n", flush=True)
    out_f = open(args.out, "a")

    def save(row):
        results.append(row)
        out_f.write(json.dumps(row, ensure_ascii=False) + "\n")
        out_f.flush()

    for i, item in enumerate(items, 1):
        if item["id"] in done_ids:
            continue
        row = {"id": item["id"], "category": item["category"], "question": item["question"]}
        a_in0, a_out0 = answer_client.tokens_in, answer_client.tokens_out
        try:
            answer, gen_latency = _retry(lambda: generate_answer(answer_client, system_prompt, item["question"]), "generate")
        except LLMError as e:
            row.update({"error": f"generation failed: {e}"})
            save(row)
            n_llm_error += 1
            print(f"[{i}/{len(items)}] {item['id']} GENERATION ERROR: {e}", file=sys.stderr)
            continue

        j_in0, j_out0 = judge_client.tokens_in, judge_client.tokens_out
        try:
            judged, judge_latency, ok, err = _retry(lambda: judge_answer(
                judge_client, judge_prompt, item["question"], item.get("must_mention", []), answer), "judge")
        except LLMError as e:
            judged, judge_latency, ok, err = None, 0.0, False, f"judge LLM error after retries: {e}"
        row["answer"] = answer
        row["gen_tokens_in"] = answer_client.tokens_in - a_in0
        row["gen_tokens_out"] = answer_client.tokens_out - a_out0
        row["gen_latency_s"] = round(gen_latency, 3)
        row["judge_latency_s"] = round(judge_latency, 3)
        row["judge_tokens_in"] = judge_client.tokens_in - j_in0
        row["judge_tokens_out"] = judge_client.tokens_out - j_out0

        if ok:
            row.update(judged)
            n_ok += 1
        else:
            row["parse_error"] = err
            n_parse_fail += 1

        save(row)
        status = "ok" if ok else "PARSE FAIL"
        score = judged["overall"] if ok else "-"
        print(f"[{i}/{len(items)}] {item['id']} ({item['category']}) -> {status}, overall={score}", flush=True)

    out_f.close()

    def _sha(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                                text=True, cwd=Path(__file__).resolve().parent.parent).stdout.strip() or None
    except Exception:
        commit = None
    meta = {
        "dataset": args.dataset, "dataset_sha256_16": _sha(args.dataset), "n_items": len(items),
        "system_prompt": args.system_prompt, "system_prompt_sha256_16": _sha(args.system_prompt),
        "judge_prompt": args.judge_prompt, "judge_prompt_sha256_16": _sha(args.judge_prompt),
        "answer_model": f"{answer_client.backend}/{answer_client.model}",
        "judge_model": f"{judge_client.backend}/{judge_client.model}",
        "mock": bool(args.mock), "git_commit": commit,
        "n_judged_ok": n_ok, "n_parse_fail": n_parse_fail, "n_generation_error": n_llm_error,
        "answer_tokens_in": answer_client.tokens_in, "answer_tokens_out": answer_client.tokens_out,
        "judge_tokens_in": judge_client.tokens_in, "judge_tokens_out": judge_client.tokens_out,
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    with open(str(args.out) + ".meta.json", "w") as mf:
        json.dump(meta, mf, indent=2)

    print(f"\nWrote {len(results)} rows to {args.out}  (+ {args.out}.meta.json)")
    print(f"  judged ok: {n_ok}  |  parse failures: {n_parse_fail}  |  generation errors: {n_llm_error}")
    if n_parse_fail:
        print(f"  ({n_parse_fail} items got no score because the judge did not return valid schema JSON — "
              f"see 'parse_error' field in the output)")


if __name__ == "__main__":
    main()
