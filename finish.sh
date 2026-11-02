#!/bin/bash
cd ~/dev/cybersec-ai-grader
while [ ! -f results/bias_report.json ]; do
  pgrep -f bias_tests >/dev/null || { echo "The bias run died before finishing - send Claude the last 10 lines of bias.log"; exit 1; }
  sleep 30
done
echo "Bias results found. Building everything..."
python3 -m harness.finalize --runs results/run_dev_v1.jsonl results/run_test_v1.jsonl --test-run results/run_test_v1.jsonl --labels data/labels_hadeel.jsonl data/labels_hajer.jsonl
python3 fill_docs.py
python3 -m harness.make_report --out report.pdf
printf "*.log\n" >> .gitignore
git rm -q --ignore-unmatch patch_*.py fix_changelog.py TODO_BEFORE_SUBMIT.md
git add -A && git commit -qm "Final results, report, README, postmortem" && echo "COMMITTED. Now open report.pdf and check it."
