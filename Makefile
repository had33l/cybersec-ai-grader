# CyberSec AI Grader - one setup command, one run command.
#   make setup      install python deps
#   make run        run system v1 + judge on dev and test sets (needs Ollama models pulled, or MOCK=1)
# Override models:  make run ANSWER_MODEL=phi3:mini JUDGE_MODEL=gemma2:9b
# Pipeline check without any LLM:  make run MOCK=1

PY            ?= python3
ANSWER_MODEL  ?= phi3:mini
JUDGE_MODEL   ?= gemma2:9b
BACKEND       ?= ollama
SYS           ?= prompts/system_prompt_v1.txt
JUDGE_PROMPT  ?= prompts/judge_prompt_v1.txt
TAG           ?= v1
N             ?= 160
LABEL_A       ?= labeller_a
LABEL_B       ?= labeller_b
ifdef MOCK
MODELS = --mock
else
MODELS = --answer-backend $(BACKEND) --answer-model $(ANSWER_MODEL) --judge-backend $(BACKEND) --judge-model $(JUDGE_MODEL)
endif
RUNNER = $(PY) harness/runner.py --system-prompt $(SYS) --judge-prompt $(JUDGE_PROMPT) $(MODELS)

.PHONY: setup data guard run v2 label-sample label-a label-b bias finalize report all changelog clean-mock

setup:
	$(PY) -m pip install -r requirements.txt --break-system-packages || $(PY) -m pip install -r requirements.txt

# needs normal internet access (Hugging Face). Overwrites data/*_set.jsonl - do this ONCE, then commit.
data:
	$(PY) data/download_real_dataset.py --n $(N)

guard:
	@if [ -f data/PLACEHOLDER_NOTICE.md ] && [ -z "$(MOCK)" ]; then \
	  echo "ERROR: data/ is still the synthetic placeholder. Run 'make data' first (see data/PLACEHOLDER_NOTICE.md)."; exit 1; fi

run: guard
	$(RUNNER) --dataset data/dev_set.jsonl  --out results/run_dev_$(TAG).jsonl
	$(RUNNER) --dataset data/test_set.jsonl --out results/run_test_$(TAG).jsonl
	$(PY) harness/report.py results/run_test_$(TAG).jsonl

v2:
	$(MAKE) run SYS=prompts/system_prompt_v2.txt TAG=v2

# build the blind labelling file from the v1 answers (judge scores are NOT included)
label-sample:
	$(PY) harness/sample_for_labelling.py --run results/run_dev_v1.jsonl results/run_test_v1.jsonl --out data/to_label.jsonl

label-a:
	$(PY) harness/label.py --in data/to_label.jsonl --out data/labels_$(LABEL_A).jsonl --labeller $(LABEL_A)
label-b:
	$(PY) harness/label.py --in data/to_label.jsonl --out data/labels_$(LABEL_B).jsonl --labeller $(LABEL_B)

bias:
	$(PY) harness/bias_tests.py --run results/run_test_v1.jsonl --dataset data/golden_set.jsonl \
	  --judge-prompt $(JUDGE_PROMPT) $(if $(MOCK),--mock,--judge-backend $(BACKEND) --judge-model $(JUDGE_MODEL)) \
	  --out results/bias_report.json

finalize:
	$(PY) -m harness.finalize --runs results/run_dev_v1.jsonl results/run_test_v1.jsonl \
	  --test-run results/run_test_v1.jsonl --labels data/labels_$(LABEL_A).jsonl data/labels_$(LABEL_B).jsonl

report: finalize
	$(PY) -m harness.make_report --out report.pdf

changelog:
	$(PY) -m harness.changelog_row $(V) $(RUN) $(if $(PREV),--prev $(PREV)) --files "$(FILES)" --change "$(CHANGE)"

# after labelling: bias tests + summary + report.pdf
all: bias report
