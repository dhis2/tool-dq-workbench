DQ Workbench — Feature highlights
============================================


Overview
========

- Purpose: Monitor and improve data quality in DHIS2
- Outputs: Numeric snapshot values of validation rules, outliers, integrity checks
- Input: DHIS2 data via Web API
- Workflow: Configure stages → run via UI/CLI → analyze in DHIS2

Architecture
============

Layers
------
- Web UI: Configure stages and run jobs
- Analyzer stages: Validation rules, Outliers, Integrity checks
- CLI/Scheduler: Automate daily runs of stages
- DHIS2 storage: Writes metrics to data elements


Server configuration
============================

Setting up the server
----------------------------
- Supports authentication via API token (only)
- Configurable concurrency. Adjust to fit your DHIS2 server capacity
- You may need to update the `maxDataQualityResults` setting on your DHIS2 instance to match the `max_results` setting in the configuration file

Server config (UI)
--------------------
.. image:: ../_static/screenshots/server_config.png
   :alt: Server configuration
   :class: r-stretch

Configuration (YAML)
--------------------
.. code-block:: yaml

   server:
     base_url: https://play.im.dhis2.org/stable-2-42-1
     d2_token: YOUR_API_TOKEN
     logging_level: INFO            # DEBUG | INFO | WARNING | ERROR
     max_concurrent_requests: 10    # limits simultaneous API calls
     max_results: 1000              # Should match maxDataQualityResults on DHIS2

Monitoring
===========

Validation Rules
----------------
- Maps a count of  validation rule violations for selected groups over a time window
- Stores a single value per org unit and period
- Aggregate counts of violations in a validation rule group to a data element

Outliers
----------
- Maps a count of outliers for a given class to a data element
- Multiple methods: Z‑score, Modified Z‑score, Min-max, Invalid numeric
- Configure time window, org unit group, and outlier class

Running an outlier stage
----------------------------


.. image:: ../_static/screenshots/outlier_stage_success.png
   :alt: Outlier stage run
   :class: r-stretch

Integrity Checks
----------------
- Maps the count of integrity violations to a data element
- Enables tracking of (meta)data integrity over time
- Support for various period types (Monthly, Weekly, Daily)

Min-max Generation
==================

Min-max Overview
--------------------
- Generates min-max ranges from historical data
- Reduces false positives in outlier detection
- Configurable lookback period and org unit group
- Configurable organisation unit levels to optimize data retrieval
- Asynchronous processing for large datasets

Min-max groups
-----------------
- Define groups of data elements for min-max generation
- The `limit median` is used to define the group
- Each group can have its own statistical method and threshold


Min-max Statistical methods
---------------------------

- Previous max: Uses the maximum value from the lookback period
- Z-score: Mean ± Threshold*stddev from the lookback period
- MAD: Median ± Threshold*MAD from the lookback period
- Box-Cox: Uses Box-Cox transformation for normality, then mean ± Threshold*stddev
- IQR: Q1 - 1.5*IQR to Q3 + 1.5*IQR from the lookback period
- Constant range: User-defined fixed min and max values


UI Highlights
=============

Stage Table
-----------
- Shows name, type, status, and actions (Run/Edit/Delete)
- “Run All” controls for integrity flow

Run Summary
-----------
- Shows execution feedback and high‑level results
- Quick sanity checks after stage runs

Screenshots (replace with yours)
--------------------------------
.. image:: ../_static/screenshots/stage_table.png
   :alt: Stage table
   :width: 80%

.. image:: ../_static/screenshots/run_summary.png
   :alt: Run summary panel
   :width: 80%

CLI & Automation
================

Scheduling
----------
- Non‑interactive CLI suitable for cron/systemd timers
- Consistent configuration → comparable daily snapshots

Command Example
---------------
.. code-block:: bash

   python -m app.web.app --config /path/to/config.yml

DHIS2 Integration
=================

API and Analytics
-----------------
- Uses DHIS2 Web API for reads/writes
- Stores metrics as standard data elements → works with dashboards/maps/pivots

Min‑Max Generation
==================

Overview
--------
- Utility to generate/update min‑max ranges from history
- Complements outlier detection and reduces false positives

Roadmap
=======

Future Enhancements
-------------------
- Rich dashboards for real‑time monitoring
- Alerts/notifications for spikes and regressions
- Extensible rule definitions and custom checks
