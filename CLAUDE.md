# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Data Quality Workbench for DHIS2 — monitors and analyzes data quality by tracking validation rule violations, outliers, and metadata integrity issues. Stores daily snapshots as numeric DHIS2 data element values. Has two modes: a CLI tool for scheduled runs and a Flask web UI for interactive configuration.

## Commands

```bash
# Setup
./setup.sh                          # Create .venv, install package in editable mode
source .venv/bin/activate
pip install -e .[dev]               # Install app + dev dependencies (pytest)

# Run tests
pytest                              # All tests (verbose by default via pytest.ini)
pytest tests/test_min_max_statistics.py::test_check_no_variance_low -v  # Single test

# Run the app
python dq_monitor.py --config config/sample_config.yml         # CLI mode
python dq_monitor.py --config config/sample_config.yml --log-level DEBUG
python -m app.web.app --config config/sample_config.yml        # Web UI

# Docs
cd docs && make html                # Sphinx HTML docs
cd docs/slides && make revealjs     # Reveal.js presentation slides
```

## Architecture

**Entry points:**
- `app/cli.py` — `DataQualityMonitor` orchestrates async execution of all configured stages, posts results back to DHIS2 via `/api/dataValueSets` (upserts + deletes)
- `app/web/app.py` — Flask application factory for the configuration/run UI

**Core flow:**
1. `app/core/config_loader.py` (`ConfigManager`) — loads and validates YAML config (structure + runtime DHIS2 connectivity)
2. Analyzer stages run concurrently via `asyncio.Semaphore` controlling `aiohttp` requests
3. Results are classified as upserts or deletes, then posted to DHIS2

**Analyzers** (`app/analyzers/`, all inherit from `StageAnalyzer`):
- `rule_analyzer.py` — validation rule violations (`/api/validationResults`)
- `outlier_analyzer.py` — outlier detection (`/api/outlierDetection`)
- `integrity_analyzer.py` — metadata integrity via dataElementGroups

**Min-max generation** (`app/minmax/`): factory pattern + statistical methods (Z-score, MAD, Box-Cox, previous-period max)

**Core utilities** (`app/core/`):
- `api_utils.py` (`Dhis2ApiUtils`) — all DHIS2 API interactions
- `period_utils.py` / `period_type.py` — DHIS2 period format handling, duration-string → date-range conversion

**Web UI** (`app/web/routes/`): stage CRUD (`edit_*.py`, `delete_*.py`), run triggers (`run.py`, `run_stage.py`), analysis views

## Configuration

YAML config has two top-level sections:
- `server`: `base_url`, `d2_token`, `logging_level`, `max_concurrent_requests`, `max_results`
- `analyzer_stages`: list of stages with `name`, `type` (`validation_rules` | `outlier` | `integrity_checks`), `level`, and type-specific `params`
- `min_max_stages`: list of stages with `datasets`, `org_units`, `groups` (statistical method + limits)

See `config/sample_config.yml` for a complete example.

## Coding Conventions

- Python 3.10+, PEP 8, 4-space indentation
- `snake_case` for files/functions/variables, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants
- Keep DHIS2 API behavior isolated in `app/core/` and analyzer helpers
- Use explicit type-safe transformations in numeric/statistical code paths
- Tests in `tests/test_*.py`, named by behavior (e.g. `test_period_boundary_for_quarterly_input`)
- Add/update tests when changing analyzer math, period parsing, or stage orchestration
