# Archived runs - NOT reproducible from the current data/

These three files were produced before the dataset was frozen. `run_v1.jsonl` was run on
items from the downloaded real dataset, but the `data/*.jsonl` files in this repo at the time
held a different (synthetic placeholder) set, and `python3 -m harness.finalize` reports
**54/54 rows whose id maps to a different question** in `data/golden_set.jsonl`.

They are kept only as an honest record (the original v1 score of 4.15 / 5 on n=54 came from here).
Do not cite them as results: re-run with `make run` on the frozen dataset.
`smoke.jsonl` and `test5.jsonl` are 5-item pipeline smoke tests.
