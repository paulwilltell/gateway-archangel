.PHONY: install run test reset-db export-approved

install:
	python -m venv .venv
	. .venv/bin/activate && pip install -r requirements.txt
	cp -n .env.example .env || true

run:
	uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

test:
	python -m pytest

reset-db:
	rm -f gateway.db

export-approved:
	python scripts/export_training_candidates.py --output training_exports/approved.jsonl
