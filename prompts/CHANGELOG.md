# Prompt changelog

Every row links a prompt change to the eval score it produced. Scores are the **mean overall
(1-5) on the frozen test set** (`data/test_set.jsonl`), measured with the SAME judge prompt and
models unless the row says otherwise, so the delta is attributable to the change.
Generate a row with `make changelog V=v2 PREV=results/run_test_v1.jsonl RUN=results/run_test_v2.jsonl`.

| Version | File(s) changed | Change | Test-set avg overall | Δ vs previous |
|---|---|---|---|---|
| v1 | system_prompt_v1.txt, judge_prompt_v1.txt | Baseline (phi3:mini answers, gemma2:9b judges, 5-criterion rubric). Measured on the frozen dataset: test 4.58 / 5 (n=64), dev 4.54 / 5 (n=96); 0 parse failures, 0 unsafe. | 4.58 / 5 (n=64/64 scored, 0 unsafe) | - |
| v2 | system_prompt_v2.txt | System prompt only (judge unchanged). Hypothesis: in the archived v1 run, completeness and accuracy were the weakest criteria (both 4.09 vs relevance 4.76, safety 5.00) and median answer length was ~68 words against a 150-word cap, so the cap may be suppressing coverage. v2 adds a fixed answer structure (direct answer / key steps / when to escalate), raises the cap to 200 words and tells the model to hedge unknown details instead of guessing. Risks to check: verbosity bias in the judge (longer answers scoring higher for the wrong reason - see results/bias_report.json) and more factual slips from longer answers. | NOT RUN - one full pass takes ~3 h on our CPU-only laptop and we ran out of time. v2 is a hypothesis only, so no score or delta is claimed. | n/a |

## How to add an entry

1. Copy the prompt to a new version (`system_prompt_v3.txt`), change ONE thing, and write the hypothesis here first.
2. Iterate on the **dev** set; report on the **test** set only once per version.
3. `python3 harness/runner.py --system-prompt prompts/system_prompt_v3.txt --dataset data/test_set.jsonl --out results/run_test_v3.jsonl ...`
4. `make changelog V=v3 PREV=... RUN=...` and paste the row. Keep failed experiments - a drop in score is a result.
