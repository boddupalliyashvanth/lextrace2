setup:
	pip install -e ".[dev]"
	python -c "from transformers import AutoModel, AutoTokenizer; [AutoTokenizer.from_pretrained(m) for m in ['sentence-transformers/all-MiniLM-L6-v2']]"

lint:
	ruff check contracts/ src/ tests/ scripts/

test:
	pytest tests/ -v --tb=short

smoke:
	echo "Running smoke tests..."
	pytest tests/contract/ tests/grounding/ -v

data:
	echo "Fetching data..."

index:
	echo "Building indexes..."

demo:
	python -m lextrace.cli demo --fake

eval:
	echo "Running eval..."
	python eval/ablate.py

ablate:
	PYTHONPATH=. python eval/ablate.py

redteam:
	pytest tests/redteam/ -v -s

audit:
	python scripts/audit_fabrication.py

heldout:
	@if [ "$${CONFIRM}" != "1" ]; then echo "Error: Must set CONFIRM=1 to run heldout"; exit 1; fi
	python scripts/run_heldout.py

judge:
	python -m lextrace.cli judge --docs $(DOCS) --queries $(QUERIES)

all: lint test redteam audit
