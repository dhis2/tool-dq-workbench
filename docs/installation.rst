Installation
============

Intended workflow
-----------------

The DQ Workbench has two distinct components with different lifetimes:

- **Web UI** — a configuration tool.  Use it to create and edit your
  ``config.yml``, then stop it.  It does not need to run permanently, and
  because it has no built-in authentication it should never be left exposed on
  a public-facing port.

- **CLI** (``dq-monitor``) — the production workload.  Once you have a
  ``config.yml``, schedule this to run daily via cron or a systemd timer.  It
  connects to DHIS2, runs the configured stages, and exits.

A typical setup looks like this:

1. A data manager runs the Web UI on their laptop to build the ``config.yml``.
2. The finished ``config.yml`` is handed to the server/system administrator.
3. The administrator schedules ``dq-monitor --config config.yml`` to run daily.

---

There are three supported ways to install the DQ Workbench, depending on your
environment and how you intend to use it.  Choose the one that suits you best:

- :ref:`install-docker` — recommended for the Web UI; no Python installation required.
- :ref:`install-venv` — recommended for production CLI runs (cron / systemd).
- :ref:`install-conda` — alternative for local use if you already use conda.

The :ref:`install-venv` and :ref:`install-conda` approaches require cloning
the repository first:

.. code-block:: bash

   git clone https://github.com/dhis2/tool-dq-workbench.git
   cd tool-dq-workbench


.. _install-docker:

Docker
------

**Requirements:** `Docker <https://docs.docker.com/get-docker/>`_.

The Docker image is the recommended way to run the **Web UI**.  A data manager
can spin it up on their laptop, point it at any DHIS2 instance, build a
``config.yml``, then shut it down — no Python installation required.

The image is published automatically to the GitHub Container Registry on every
push to ``main`` and on tagged releases:

.. code-block:: bash

   docker pull ghcr.io/dhis2/tool-dq-workbench:latest

Quick start (remote DHIS2)
^^^^^^^^^^^^^^^^^^^^^^^^^^

This is the primary use case.  One command is all you need:

.. code-block:: bash

   docker run --rm -p 127.0.0.1:5000:5000 \
     -e DHIS2_BASE_URL=https://your-dhis2-instance.org \
     -e DHIS2_API_TOKEN=d2p_your_token_here \
     -v $(pwd)/config:/app/config \
     ghcr.io/dhis2/tool-dq-workbench:latest

The web UI will be available at ``http://localhost:5000``.

- If no ``config.yml`` exists in the mounted volume, one is **bootstrapped
  automatically** from the environment variables.
- The ``-v`` volume mount persists your configuration across container restarts.
  Omit it if you only need a temporary session.
- Stop the container with ``Ctrl-C``.

.. warning::

   The web UI has no built-in authentication.  Only run it on localhost or a
   trusted network, and stop it once you have finished editing your
   configuration.

Quick start (local DHIS2 on Linux)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If your DHIS2 instance is running locally on the same machine, use
``--network host`` so the container can reach it via ``localhost``:

.. code-block:: bash

   docker run --rm --network host \
     -e DHIS2_BASE_URL=http://localhost:8080 \
     -e DHIS2_API_TOKEN=d2p_your_token_here \
     -v $(pwd)/config:/app/config \
     ghcr.io/dhis2/tool-dq-workbench:latest

The web UI will be available at ``http://localhost:5000``.

.. note::

   ``--network host`` is a Linux-only Docker feature.  On macOS or Windows use
   ``host.docker.internal`` in place of ``localhost`` in the URL.

Optional: stable Flask session key
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

By default a random session key is generated at startup, which means browser
sessions are invalidated whenever the container restarts.  To avoid this, pass
a stable key:

.. code-block:: bash

   export FLASK_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

   docker run --rm -p 127.0.0.1:5000:5000 \
     -e DHIS2_BASE_URL=https://your-dhis2-instance.org \
     -e DHIS2_API_TOKEN=d2p_your_token_here \
     -e FLASK_SECRET_KEY \
     -v $(pwd)/config:/app/config \
     ghcr.io/dhis2/tool-dq-workbench:latest

Using Docker Compose (advanced)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

For a more permanent setup, copy the example environment file and use
Docker Compose:

.. code-block:: bash

   cp .env.example .env

Edit ``.env`` and set ``DHIS2_BASE_URL``, ``DHIS2_API_TOKEN``, and
optionally ``FLASK_SECRET_KEY``.

Start the web UI:

.. code-block:: bash

   docker compose --profile web up

Run the CLI on demand:

.. code-block:: bash

   docker compose run --rm cli

Schedule the CLI daily via cron (``crontab -e``):

.. code-block:: text

   0 6 * * * cd /path/to/tool-dq-workbench && docker compose run --rm cli >> /var/log/dq-monitor.log 2>&1

.. note::

   For production scheduled runs (cron / systemd), a direct install via
   :ref:`install-venv` is simpler than Docker — fewer moving parts and no
   container networking to manage.


.. _install-conda:

Conda
-----

**Requirements:** `conda <https://docs.conda.io/en/latest/miniconda.html>`_ or
`mamba <https://mamba.readthedocs.io/>`_.  This is the recommended approach for
local use — conda manages the Python version and the scientific stack (NumPy,
SciPy, pandas) automatically.

1. Create and activate the environment:

   .. code-block:: bash

      conda env create -f environment.yml
      conda activate dq-workbench

2. Copy and edit the sample configuration file:

   .. code-block:: bash

      cp config/sample_config.yml config/my_config.yml

3. Run the web UI:

   .. code-block:: bash

      gunicorn "app.web.app:create_app('config/my_config.yml')" --bind 0.0.0.0:5000 --timeout 300

   The web UI will be available at ``http://localhost:5000``.

4. Or run the CLI directly:

   .. code-block:: bash

      dq-monitor --config config/my_config.yml


.. _install-venv:

Python virtual environment
--------------------------

**Requirements:** Python 3.10 or later.

1. Run the setup script (creates ``.venv`` and installs the package):

   .. code-block:: bash

      ./setup.sh
      source .venv/bin/activate

   Or manually:

   .. code-block:: bash

      python3 -m venv .venv
      source .venv/bin/activate   # On Windows: .venv\Scripts\activate
      pip install -e .

2. Copy and edit the sample configuration file:

   .. code-block:: bash

      cp config/sample_config.yml config/my_config.yml

3. Run the web UI:

   .. code-block:: bash

      gunicorn "app.web.app:create_app('config/my_config.yml')" --bind 0.0.0.0:5000 --timeout 300

   .. note::

      Do not use ``python -m app.web.app`` in production — it starts Flask's
      built-in development server, which is not safe or stable for production use.
      Pass ``--debug`` if you need debug mode during development.


.. _flask-secret-key:

Flask secret key
----------------

The web UI uses a secret key to sign session cookies.  If ``FLASK_SECRET_KEY``
is not set, a random key is generated at startup — sessions will be lost on
container or process restart.  For a stable key:

.. code-block:: bash

   python3 -c "import secrets; print(secrets.token_hex(32))"

Set this value in your ``.env`` file (Docker Compose), as a ``-e`` flag
(``docker run``), or exported in your shell before launching gunicorn.
