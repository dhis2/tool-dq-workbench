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

- :ref:`install-docker` — recommended for server deployment or if you already use Docker.
- :ref:`install-conda` — recommended for local/laptop use, especially if you work in data science.
- :ref:`install-venv` — for those who prefer a plain Python virtual environment.

All three approaches require cloning the repository first:

.. code-block:: bash

   git clone https://github.com/dhis2/tool-dq-workbench.git
   cd tool-dq-workbench


.. _install-docker:

Docker
------

**Requirements:** `Docker <https://docs.docker.com/get-docker/>`_ and Docker Compose.

1. Copy the example environment file and fill in your secrets:

   .. code-block:: bash

      cp .env.example .env

   Edit ``.env`` and set ``DHIS2_API_TOKEN`` and ``FLASK_SECRET_KEY``.  See
   :ref:`flask-secret-key` for how to generate a secure key.

2. Copy and edit the sample configuration file:

   .. code-block:: bash

      cp config/sample_config.yml config/config.yml

   Set ``base_url`` to your DHIS2 instance and set ``d2_token: ${DHIS2_API_TOKEN}``
   so the token is read from the environment rather than stored in the file.

3. **Create your configuration using the Web UI.**  Start it when you need it
   and stop it when you are done:

   .. code-block:: bash

      docker compose --profile web up

   The web UI will be available at ``http://localhost:5000``.  Stop it with
   ``Ctrl-C`` (or ``docker compose --profile web down`` in another terminal).

   .. warning::

      The web UI has no built-in authentication.  Only run it on localhost or
      a trusted network, and stop it once you have finished editing your
      configuration.

4. **Run the CLI.**  Once you have a ``config.yml``, run the CLI on demand:

   .. code-block:: bash

      docker compose run --rm cli

   To schedule it daily via cron, add a line like this to your crontab
   (``crontab -e``):

   .. code-block:: text

      0 6 * * * cd /path/to/tool-dq-workbench && docker compose run --rm cli >> /var/log/dq-monitor.log 2>&1


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

The web UI uses a secret key to sign session cookies.  For Docker and venv
deployments, set the ``FLASK_SECRET_KEY`` environment variable to a random
value before starting the server:

.. code-block:: bash

   python -c "import secrets; print(secrets.token_hex(32))"

For Docker Compose, add this value to your ``.env`` file.  For a venv
deployment, export it in your shell or service unit before launching gunicorn.
