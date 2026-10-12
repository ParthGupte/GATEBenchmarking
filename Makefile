PYTHON ?= python3
EXTRACT_OUT ?= build/extracted

.PHONY: all score figures tables reports verify extract benchmark clean help

## all: rebuild every figure and table from the committed data (free, ~1 min)
all: score figures tables

## score: grade data/responses/ against the answer keys -> results/
score:
	$(PYTHON) -m gatebench.score

## figures: regenerate Figures 1-9 plus the cost/time figures -> figures/
figures:
	$(PYTHON) -m gatebench.plot_figures
	$(PYTHON) -m gatebench.plot_cost_time
	$(PYTHON) -m gatebench.plot_single_model_ga

## tables: regenerate Tables I and II -> tables/cost_time_tables.tex
tables:
	$(PYTHON) -m gatebench.build_tables

## reports: build the per-question spreadsheet and the qualitative dumps
reports:
	$(PYTHON) -m gatebench.build_excel_report
	$(PYTHON) -m gatebench.extract_mta_answers
	$(PYTHON) -m gatebench.find_gemini_succeeds_gpt_fails

## verify: check dataset invariants and re-parse the PDFs to check extraction
verify:
	$(PYTHON) -m gatebench.verify

## extract: re-run PDF extraction into $(EXTRACT_OUT) (does NOT touch data/)
extract:
	@echo "Extracting into $(EXTRACT_OUT)/ -- data/ is left untouched."
	@echo "The committed question bank is manually reviewed; see README."
	GATEBENCH_EXTRACT_OUT=$(EXTRACT_OUT) $(PYTHON) -m gatebench.extract_answer_keys
	GATEBENCH_EXTRACT_OUT=$(EXTRACT_OUT) $(PYTHON) -m gatebench.extract_questions
	GATEBENCH_EXTRACT_OUT=$(EXTRACT_OUT) $(PYTHON) -m gatebench.extract_images

## benchmark: re-query the models via the OpenRouter API (COSTS REAL MONEY)
benchmark:
	@echo "This calls paid APIs. A full sweep is roughly \$$60."
	@echo "Showing the worklist only; add --yes to actually run:"
	@echo "    $(PYTHON) -m gatebench.run_benchmark --yes"
	$(PYTHON) -m gatebench.run_benchmark --dry-run

## clean: remove generated outputs (not the committed data)
clean:
	rm -rf build/ $(EXTRACT_OUT)
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

## help: list the available targets
help:
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/## //'
