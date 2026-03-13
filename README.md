# Data Quality Workbench for DHIS2

A tool for monitoring data quality in DHIS2 by tracking validation rule violations,
outliers, and metadata integrity issues over time. Results are stored as regular data values
in DHIS2 data elements, making them available for analysis in maps, charts, and pivot tables.

## Quick start

The fastest way to get started is with Docker. You only need a DHIS2 instance and a
personal access token.

**Remote DHIS2:**

```bash
docker run --rm -p 127.0.0.1:5001:5000 \
  -e DHIS2_BASE_URL=https://your-dhis2-instance.org \
  -e DHIS2_API_TOKEN=d2p_your_token_here \
  -v $(pwd)/config:/app/config \
  ghcr.io/dhis2/tool-dq-workbench:latest
```

**Local DHIS2 (also running in Docker):**

If your DHIS2 is running locally via Docker, `localhost` inside the workbench
container won't reach it — use `host.docker.internal` instead:

```bash
docker run --rm -p 127.0.0.1:5001:5000 \
  --add-host=host.docker.internal:host-gateway \
  -e DHIS2_BASE_URL=http://host.docker.internal:8080 \
  -e DHIS2_API_TOKEN=d2p_your_token_here \
  -v $(pwd)/config:/app/config \
  ghcr.io/dhis2/tool-dq-workbench:latest
```

> **macOS/Windows:** `--add-host` is not needed — `host.docker.internal` works out of the box.

**Local DHIS2 (running directly on Linux, not in Docker):**

```bash
docker run --rm --network host \
  -e DHIS2_BASE_URL=http://localhost:8080 \
  -e DHIS2_API_TOKEN=d2p_your_token_here \
  -v $(pwd)/config:/app/config \
  ghcr.io/dhis2/tool-dq-workbench:latest
```

Open http://localhost:5001 in your browser. A configuration file will be created
automatically in `./config` on first run.

> **Note:** The web UI has no built-in authentication. Only run it on localhost or
> a trusted network, and stop it when you are done.

## How it works

The workbench has two components:

- **Web UI** — use it to create and edit your `config.yml`, then stop it.
- **CLI** (`dq-monitor`) — run this on a schedule (e.g. daily via cron) to collect
  data quality snapshots and post them to DHIS2.

A typical workflow:
1. A data manager runs the Web UI to build a `config.yml`.
2. The `config.yml` is handed to a system administrator.
3. The administrator schedules `dq-monitor --config config.yml` to run daily.

## Running the CLI

Once you have a `config.yml`, run the CLI directly (recommended for scheduled use):

```bash
pip install git+https://github.com/dhis2/tool-dq-workbench.git
dq-monitor --config config/my_config.yml
```

Or via Docker:

```bash
docker compose run --rm cli
```

## Documentation

Full documentation including configuration reference, stage types, and min-max
generation is available in the `docs/` directory:

```bash
cd docs && make html
```

Or read the source in `docs/*.rst`.
