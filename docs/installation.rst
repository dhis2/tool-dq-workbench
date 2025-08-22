Installation
==================


Runtime Requirements
------------------
In order to run either the command line script or the Web UI,
you will need to have the following installed:
- Python 3.8 or later
- pip (Python package installer)
- A web browser (for the Web UI)
- A terminal or command prompt (for the command line script)
- A supported operating system (Linux, macOS, or Windows)

Installation Steps
------------------
1. **Clone the repository**:
   Open your terminal or command prompt and run:
   ```
   git clone git@github.com:dhis2/tool-dq-workbench.git
   ```

2. **Navigate to the project directory**:
   Change into the cloned directory:
   ```
   cd tool-dq-workbench
   ```

**Create a virtual environment** (optional but recommended):
    You can create a virtual environment to isolate the project dependencies:
    ```
    python -m venv venv
    ```

    Activate the virtual environment:
    - On Windows:
      ```
      venv\Scripts\activate
      ```
    - On macOS/Linux:
      ```
      source venv/bin/activate
      ```

4. **Install the run time dependencies**:
   Run the installation script to set up the environment:
   ```
   pip install -e .
   ```

5. **Install the development dependencies** (optional):
   If you want to contribute to the project or run tests, install the development dependencies:
   ```
   pip install -e .[dev]
   ```

6. **Modify the sample configuration file**:
    A sample configuration file is provided in the `config` directory.
   You can copy it to your working directory and modify it as needed:
    ```
    cp config/sample_config.json config/config.json
    ```

7. **Change the configuration file**:
   Open `config/config.yml` in a text editor and modify the settings as needed for your environment.
At the very least, you will need to set the `base_url` and `base_url` fields to point to your DHIS2 instance. Further
changes to the configuration file can be performed with the web UI.

For the `base_url` field, you can use the following format:
   ```
   "base_url": "https://play.im.dhis2.org/stable-2-42-1"
   ```
Note that the `base_url` should not include a trailing slash.


8. **Run the Web UI**:
   You can now run the command line script or start the Web UI:
   - For the Web UI, run:
     ```
     python -m app.web.app --config config/config.yml
     ```