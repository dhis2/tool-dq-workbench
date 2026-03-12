# Repository Guidelines

## Project Structure & Module Organization
Core application code lives under `app/`.
- `app/cli.py` is the CLI entrypoint used by `dq-monitor`.
- `app/analyzers/` contains stage analyzers (validation rules, outliers, integrity checks).
- `app/minmax/` contains min-max generation/statistics logic.
- `app/core/` contains shared utilities (period handling, config loading, API helpers).
- `app/web/` contains the Flask UI (`routes/`, `templates/`, `static/`).

Tests are in `tests/` and documentation is in `docs/` (plus `docs/slides/` for reveal.js slides).
Runtime/config artifacts are typically kept in `config/` and `metadata/`.

## Build, Test, and Development Commands
- `./setup.sh`: create `.venv`, upgrade `pip`, and install the package in editable mode.
- `source .venv/bin/activate`: activate local environment.
- `pip install -e .[dev]`: install app + dev dependencies manually.
- `pytest`: run the test suite (`pytest.ini` sets `testpaths=tests` and verbose output).
- `python dq_monitor.py --help`: run the CLI wrapper directly.
- `cd docs && make html`: build Sphinx HTML docs.
- `cd docs/slides && make revealjs`: build presentation slides.

## Coding Style & Naming Conventions
Use Python 3.10+ and 4-space indentation. Follow PEP 8 and keep functions small and single-purpose.
- Files/modules: `snake_case.py`
- Functions/variables: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`

Prefer explicit type-safe transformations for numeric/statistical code paths, and keep DHIS2 API behavior isolated in analyzer/core helpers.

## Testing Guidelines
Use `pytest` for all tests.
- Place tests in `tests/` as `test_*.py`.
- Name tests by behavior (example: `test_period_boundary_for_quarterly_input`).
- Add or update tests when changing analyzer math, period parsing, or stage orchestration.

Run `pytest -v` locally before opening a PR.

## Commit & Pull Request Guidelines
Recent history favors short, imperative commit messages (example: `Fix bug with min/max stage deletion`). Keep commits focused and atomic.

For pull requests, include:
- what changed and why,
- impacted modules/configs,
- test evidence (`pytest` output),
- screenshots for UI/template changes (`app/web/templates` or static assets),
- linked issue/ticket when available.
