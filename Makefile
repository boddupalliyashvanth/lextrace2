setup:
	pip install -e ".[dev]"
	python -c "from transformers import AutoModel, AutoTokenizer; [AutoTokenizer.from_pretrained(m) for m in ['sentence-transformers/all-MiniLM-L6-v2']]"

lint:
	ruff check contracts/ src/ tests/
	mypy contracts/

test:
	pytest tests/

smoke:
	echo "Running smoke tests..."

data:
	echo "Fetching data..."

index:
	echo "Building indexes..."

demo:
	python -m lextrace.cli demo --fake

eval:
	echo "Running eval..."

ablate:
	echo "Running ablate..."

redteam:
	echo "Running redteam..."

judge:
	python -m lextrace.cli judge --docs $(DOCS) --queries $(QUERIES)

heldout:
	@if [ "$${CONFIRM}" != "1" ]; then echo "Error: Must set CONFIRM=1 to run heldout"; exit 1; fi
	echo "Running heldout..."
