Installation
============


Runtime Requirements
--------------------
In order to run either the command line script or the Web UI,
you will need to have the following installed:
- Python 3.8 or later
- pip (Python package installer)
- A web browser (for the Web UI)
- A terminal or command prompt (for the command line script)
- A supported operating system (Linux, macOS, or Windows)

Installation Steps
------------------

1. Clone the repository:

   .. code-block:: bash

      git clone git@github.com:dhis2/tool-dq-workbench.git

2. Navigate to the project directory:

   .. code-block:: bash

      cd tool-dq-workbench

3. Create a virtual environment (recommended):

   .. code-block:: bash

      python -m venv .venv

   Activate the virtual environment:

   - On Windows:

     .. code-block:: bat

        .venv\Scripts\activate

   - On macOS/Linux:

     .. code-block:: bash

        source .venv/bin/activate

4. Install runtime dependencies:

   .. code-block:: bash

      pip install -e .

5. Install development dependencies (optional):

   .. code-block:: bash

      pip install -e .[dev]

6. Copy and edit the sample configuration file:

   .. code-block:: bash

      cp config/sample_config.yml /home/bobbytables/dq-workbench/my_config.yml

   Open ``/home/bobbytables/dq-workbench/my_config.yml`` in a text editor and modify the settings for your environment.
   At minimum, set ``base_url`` to point to your DHIS2 instance. The value should not include a trailing slash, for example:

   .. code-block:: json

      {
        "base_url": "https://play.im.dhis2.org/stable-2-42-1"
      }

7. Run the Web UI:

   .. code-block:: bash

      python -m app.web.app --config /home/bobbytables/dq-workbench/my_config.yml
