.PHONY: setup scrape-new scrape-full classify classify-status dashboard stats test

# Setup
setup:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt
	.venv/bin/playwright install chromium

setup-dev:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements-dev.txt
	.venv/bin/playwright install chromium

# Scraping
scrape-new:
	PYTHONUNBUFFERED=1 python main.py scrape --new

scrape-full:
	PYTHONUNBUFFERED=1 python main.py scrape --full

scrape-keyword:
	@test -n "$(KEYWORD)" || (echo "Usage: make scrape-keyword KEYWORD='machine learning'" && exit 1)
	PYTHONUNBUFFERED=1 python main.py scrape --keyword "$(KEYWORD)"

# Classification
classify:
	python -m classifier.ai

classify-status:
	python -m classifier.ai --status

# Dashboard & Reporting
dashboard:
	streamlit run dashboard/app.py

stats:
	python main.py stats

# Testing
test:
	pytest tests/ -v

# Database
db-count:
	python -c "from database.db import get_job_count, init_db; init_db(); print(get_job_count())"

db-categories:
	sqlite3 data/jobs.db "SELECT category, COUNT(*) FROM jobs WHERE category != '' GROUP BY category ORDER BY COUNT(*) DESC"
