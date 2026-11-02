# CyberSec AI Grader

CS496 AI Engineering - Project 1 (The Grader). An evaluation harness for a prompted system that answers
practical cybersecurity questions for non-experts. Answers are graded by an LLM judge (accuracy, relevance,
clarity, completeness, safety, overall; 1-5), and the judge itself is tested against human labels and for
position and verbosity bias.

**The harness is the deliverable.** The system (phi3:mini with a prompt) exists to be measured.

## Setup (one command)

```bash
make setup                         # pip install -r requirements.txt
```
Models run locally with [Ollama](https://ollama.com) (no API key needed):
```bash
ollama pull phi3:mini              # answerer
ollama pull gemma2:9b              # judge (a different model on purpose)
```
Hosted alternative (any OpenAI-compatible endpoint; the key is read from the environment only, never committed):
`export OPENAI_API_KEY=...; make run BACKEND=openai ANSWER_MODEL=<model> JUDGE_MODEL=<model>`

## Run (one command)

```bash
make run                           # system v1 + judge on data/dev_set.jsonl and data/test_set.jsonl
make run MOCK=1                    # same pipeline with fake in-process LLMs (checks the harness, needs no models)
```
Each run writes one row per item (input, answer, 5 criterion scores, overall, reason, unsafe flag, latency, tokens) to
`results/run_{dev,test}_v1.jsonl`, plus a `.meta.json` (dataset hash, prompt hashes, models, git commit). Runs save every row
as they finish and **resume automatically** if interrupted; LLM errors and timeouts are retried.

Note: a run resumes from its existing results file, so on this repo `make run` reuses the committed v1 results. To re-run the models from scratch, delete `results/run_dev_v1.jsonl*` and `results/run_test_v1.jsonl*` first (about 6 hours on a CPU-only laptop).

Reproduce the evaluation from the committed files (no models needed):
```bash
python3 -m harness.finalize --runs results/run_dev_v1.jsonl results/run_test_v1.jsonl --test-run results/run_test_v1.jsonl \
  --labels data/labels_hadeel.jsonl data/labels_hajer.jsonl
python3 -m harness.make_report --out report.pdf
```
Other steps: `make label-sample`, `make label-a`, `make bias`, `make report` (see the Makefile).

## Repository layout

```
data/        golden_set.jsonl (160), dev_set.jsonl (96), test_set.jsonl (64), labelling_guide.md,
             to_label.jsonl (blind labelling file), labels_hadeel.jsonl, labels_hajer.jsonl
harness/     runner.py, judge.py, schema.py (fixed JSON schema), llm_client.py, system_under_test.py, label.py,
             agreement.py, bias_tests.py, finalize.py, cost.py, make_report.py, changelog_row.py, report.py
prompts/     system_prompt_v1.txt, system_prompt_v2.txt (written, NOT run), judge_prompt_v1.txt, CHANGELOG.md
results/     run_{dev,test}_v1.jsonl (+ .meta.json), bias_report.json, summary.json, dropped_items.md,
             archive_unreproducible/ (early runs that do not match the frozen data; kept for honesty, not cited)
report.pdf   4 pages max, generated from results/summary.json
postmortem.md
cost_assumptions.json   editable price / machine-cost assumptions for the cost model
```

## How the pieces answer the brief

| Requirement | Where |
|---|---|
| 150+ item golden set, dev/test split, jsonl | `data/` - 160 items (96 dev / 64 test), frozen and committed |
| Labelling guide with examples | `data/labelling_guide.md` |
| Labelled by two people, agreement reported | `data/labels_*.jsonl`, `harness/agreement.py` / `finalize.py` (numbers below) |
| One result per item, structured output | `harness/runner.py`, `harness/schema.py` (judge returns a fixed JSON schema; 2 retries, then logged as parse failure) |
| Judge vs human agreement | Results below / `results/summary.json` |
| Position bias, verbosity bias | `harness/bias_tests.py` -> `results/bias_report.json` |
| Prompts under version control + changelog | `prompts/`, git history, `prompts/CHANGELOG.md` |
| Cost per 1k requests, today and at 100x | `harness/cost.py`, `cost_assumptions.json`, report section 6 |

## Data source

Questions, expert reference answers and rubrics (`must_mention`) come from the Hugging Face dataset
**Rowden/CybersecurityQAA** (see `data/labelling_guide.md` for the citation and licence note), downloaded and split once by
`data/download_real_dataset.py`. The dataset was then **frozen and committed**; never re-run the downloader, because it
renumbers ids and would silently invalidate every result. Each run's `.meta.json` stores the dataset hash and
`harness/finalize.py` warns if result ids do not match `golden_set.jsonl`. The system's answers and all human scores were
produced by us.

## Results

<!--AUTO:RESULTS-->
_(generated from results/summary.json and results/bias_report.json by `fill_docs.py`)_

**System score (v1, phi3:mini answers, gemma2:9b judge)**
- Test set (results/run_test_v1.jsonl): mean overall **4.578 / 5** over 64/64 items; overall 1/2/3/4/5 = 0/0/7/13/44 (68.8% scored 5); 0 flagged unsafe; 0 failures.
- Dev set (results/run_dev_v1.jsonl): mean overall **4.542 / 5** over 96/96 items; overall 1/2/3/4/5 = 0/4/7/18/67 (69.8% scored 5); 0 flagged unsafe; 0 failures.

**Human labels**
- Two labellers scored 160 items each; 0 dropped.
- Human vs human: exact 64/160 (40.0%), within 1 point 130/160 (81.2%), Cohen's kappa 0.066; mean difference 0.42 (hadeel minus hajer); 30 items (18.8%) differed by 2+ points (listed in results/dropped_items.md).

**Judge vs humans**
- judge vs hadeel (n=160): exact 30/160 (18.8%), within 1 point 142/160 (88.8%), Cohen's kappa 0.006; judge minus human on average +0.81.
- judge vs hajer (n=160): exact 28/160 (17.5%), within 1 point 102/160 (63.8%), Cohen's kappa -0.023; judge minus human on average +1.23.
- judge vs consensus(rounded mean) (n=130): exact 39/130 (30.0%), within 1 point 120/130 (92.3%), Cohen's kappa 0.041; judge minus human on average +0.69.

**Judge bias**
- **Position bias** (system answer vs the expert reference, both orders, n=20 pairs): 7 of 20 verdicts changed when the order was swapped (35.0%, a large flip rate); 13 were consistent. The judge picked the first slot in 27/40 verdicts (67.5%), i.e. it favours the answer shown FIRST. 0 pairs were skipped (unparseable or LLM errors).
- **Verbosity bias** (same answer + one filler sentence, n=20): score rose on 0, unchanged on 20, dropped on 0. 13 of the 20 items already scored 5 and could not rise, so the fairer figure is **0 of 7 items below 5 (0.0%) rose**. No strong verbosity effect was detected, but the test is weak because of the ceiling effect.

**Cost** (measured tokens/latency; prices are assumptions in `cost_assumptions.json`)
- Mean tokens/item: generation 176.2 in / 183.8 out; judge 555.1 in / 68.9 out.
- Latency (CPU-only laptop): generation median 25.97s, judge median 47.44s.
- Per 1k requests: hosted small model $0.1367 (answer only) / $0.2613 (answer+judge); local machine $2.5015 / $7.5258.
- At 100x (100000 requests): hosted $13.67, local $250.15; serving that volume sequentially on this laptop would take about 34.7 days.
<!--/AUTO:RESULTS-->

Prompt iteration: only the v1 baseline was measured. `system_prompt_v2.txt` is written with a recorded hypothesis but was **not run**
(one full pass takes about 3 hours on our CPU-only laptop), so no v1-to-v2 change is claimed. See `prompts/CHANGELOG.md`.

## Postmortem

See `postmortem.md`.


## Notes

- No API keys are stored in this repo; `OPENAI_API_KEY` is only read from the environment.
- Local inference: CPU only, 16 GB RAM, so models are slow (see Cost). Do not run two jobs against Ollama at once - that
  crashed it repeatedly (see postmortem).
