# Windows Installer (PyInstaller + Inno Setup) Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package the DQ Workbench web UI as a Windows `.exe` installer so non-technical users can install and run it by double-clicking, with no command-line interaction required.

**Architecture:** PyInstaller `--onedir` bundles the Flask app + all dependencies into a directory; Inno Setup wraps that directory into a standard Windows installer wizard; a GitHub Actions `windows-latest` workflow builds the installer automatically on every version tag. The Flask dev server is replaced with `waitress` (cross-platform WSGI server). The existing zero-config startup feature handles first-run config creation automatically.

**Tech Stack:** Python 3.11, waitress 3.x, PyInstaller 6.x, Inno Setup 6, GitHub Actions

---

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `pyproject.toml` | Modify | Add `waitress` dep; add `sys_platform != 'win32'` marker to `gunicorn` |
| `app/web/app.py` | Modify | Replace `app.run()` with `waitress.serve()`; add `sys.frozen` path fix in `create_app()` |
| `installer/main_win.py` | Create | Clean PyInstaller entry point |
| `installer/dq_workbench.spec` | Create | PyInstaller spec: declares templates/static assets and hidden imports |
| `installer/dq_workbench_win.iss` | Create | Inno Setup script: installer wizard, shortcuts, uninstaller |
| `.github/workflows/windows-installer.yml` | Create | CI: builds `.exe` on every `v*` tag and attaches to GitHub Release |
| `tests/test_web_app_waitress.py` | Create | Tests for waitress integration and PyInstaller path resolution |

---

## Chunk 1: Python Changes

### Task 1: Add waitress dependency

**Files:**
- Modify: `pyproject.toml:10-22`

- [ ] **Step 1: Update pyproject.toml**

  Replace the `gunicorn` line and add `waitress`:

  ```toml
  "gunicorn>=23,<25; sys_platform != 'win32'",
  "waitress>=3.0,<4",
  ```

  The `sys_platform != 'win32'` marker means gunicorn silently skips installation on Windows (it is Linux/macOS only). `waitress` installs everywhere.

- [ ] **Step 2: Reinstall the package**

  ```bash
  pip install -e .
  ```

  Expected: no errors. `waitress` appears in `pip list`.

- [ ] **Step 3: Verify waitress is importable**

  ```bash
  python -c "from waitress import serve; print('waitress ok')"
  ```

  Expected: `waitress ok`

- [ ] **Step 4: Commit**

  ```bash
  git add pyproject.toml
  git commit -m "feat: add waitress dep; restrict gunicorn to non-Windows"
  ```

---

### Task 2: Replace app.run() with waitress in main()

**Files:**
- Modify: `app/web/app.py`
- Create: `tests/test_web_app_waitress.py`

The current `main()` ends with `app.run(debug=args.debug, use_reloader=False)`. Replace it with `waitress.serve()` and add an auto-open browser call.

Move three imports to module level (required for test mocking):

- [ ] **Step 1: Write the failing test**

  Create `tests/test_web_app_waitress.py`:

  ```python
  # tests/test_web_app_waitress.py
  import sys
  import yaml
  import pytest
  from unittest.mock import patch, call


  @pytest.fixture
  def config_file(tmp_path):
      cfg = tmp_path / "config.yml"
      cfg.write_text(yaml.dump({
          'server': {
              'base_url': 'https://dhis2.example.org',
              'd2_token': 'fake-token',
              'logging_level': 'INFO',
              'max_concurrent_requests': 5,
              'max_results': 500,
          },
          'analyzer_stages': [],
      }))
      return str(cfg)


  def test_main_serves_via_waitress(config_file, monkeypatch):
      """main() must use waitress.serve, not app.run()."""
      monkeypatch.setattr(sys, 'argv', ['prog', '--config', config_file, '--skip-validation'])
      with patch('app.web.app.serve') as mock_serve, \
           patch('app.web.app.threading') as mock_threading:
          from app.web.app import main
          main()
      mock_serve.assert_called_once()
      _, kwargs = mock_serve.call_args
      assert kwargs['host'] == '127.0.0.1'
      assert kwargs['port'] == 5000


  def test_main_opens_browser(config_file, monkeypatch):
      """main() must schedule a browser open via threading.Timer."""
      monkeypatch.setattr(sys, 'argv', ['prog', '--config', config_file, '--skip-validation'])
      with patch('app.web.app.serve'), \
           patch('app.web.app.threading') as mock_threading:
          from app.web.app import main
          main()
      mock_threading.Timer.assert_called_once()
      timer_args = mock_threading.Timer.call_args[0]
      assert timer_args[0] == 1.5   # delay in seconds
  ```

- [ ] **Step 2: Run test to verify it fails**

  ```bash
  pytest tests/test_web_app_waitress.py -v
  ```

  Expected: FAIL — `app.web.app` has no attribute `serve` or `threading`.

- [ ] **Step 3: Update app/web/app.py**

  **Add three imports at the top of the file** (after `import os`, before `from flask import Flask`):

  ```python
  import threading
  import webbrowser
  from waitress import serve
  ```

  **Replace the last line of `main()`** — change:
  ```python
  app.run(debug=args.debug, use_reloader=False)
  ```
  to:
  ```python
  threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
  print("=" * 60)
  print("DQ Workbench is running at http://127.0.0.1:5000")
  print("Close this window to stop the server.")
  print("=" * 60)
  serve(app, host="127.0.0.1", port=5000)
  ```

- [ ] **Step 4: Run tests to verify they pass**

  ```bash
  pytest tests/test_web_app_waitress.py -v
  ```

  Expected: PASS (both tests green)

- [ ] **Step 5: Run full test suite to check for regressions**

  ```bash
  pytest
  ```

  Expected: same pass/fail count as before (the known `test_values_boxcox_with_zero` failure is pre-existing and unrelated)

- [ ] **Step 6: Commit**

  ```bash
  git add app/web/app.py tests/test_web_app_waitress.py
  git commit -m "feat: serve via waitress with auto-open browser"
  ```

---

### Task 3: Add PyInstaller path resolution in create_app()

**Files:**
- Modify: `app/web/app.py:121-130`
- Modify: `tests/test_web_app_waitress.py` (add one test)

When running as a PyInstaller `--onedir` bundle, `sys.frozen` is set to `True` and Flask cannot find templates/static at their normal package-relative paths. We must point Flask to the correct locations inside the bundle.

**How PyInstaller `--onedir` works:** All files (including templates/static declared in `datas`) are placed next to the executable in the bundle directory. `os.path.dirname(sys.executable)` gives us that directory. If `sys._MEIPASS` is set (some PyInstaller versions also set it for `--onedir`), we prefer it; otherwise fall back to `dirname(sys.executable)`.

- [ ] **Step 1: Write the failing test**

  Append to `tests/test_web_app_waitress.py`:

  ```python
  def test_create_app_uses_bundle_paths_when_frozen(tmp_path, monkeypatch):
      """create_app() must use bundle paths for templates/static when sys.frozen is set."""
      import os
      cfg = tmp_path / "config.yml"
      cfg.write_text(yaml.dump({
          'server': {
              'base_url': '',
              'd2_token': '',
              'logging_level': 'INFO',
              'max_concurrent_requests': 5,
              'max_results': 500,
          },
          'analyzer_stages': [],
      }))
      fake_bundle_dir = str(tmp_path / 'bundle')
      monkeypatch.setattr(sys, 'frozen', True, raising=False)
      monkeypatch.setattr(sys, '_MEIPASS', fake_bundle_dir, raising=False)

      from app.web.app import create_app
      flask_app = create_app(str(cfg), skip_validation=True)

      assert flask_app.template_folder == os.path.join(fake_bundle_dir, 'app', 'web', 'templates')
      assert flask_app.static_folder == os.path.join(fake_bundle_dir, 'app', 'web', 'static')


  def test_create_app_uses_normal_paths_when_not_frozen(tmp_path, monkeypatch):
      """create_app() must use standard Flask paths when not running as a bundle."""
      cfg = tmp_path / "config.yml"
      cfg.write_text(yaml.dump({
          'server': {
              'base_url': '',
              'd2_token': '',
              'logging_level': 'INFO',
              'max_concurrent_requests': 5,
              'max_results': 500,
          },
          'analyzer_stages': [],
      }))
      # Ensure sys.frozen is NOT set
      monkeypatch.delattr(sys, 'frozen', raising=False)

      from app.web.app import create_app
      flask_app = create_app(str(cfg), skip_validation=True)

      # Flask default: template_folder is 'templates' (relative)
      assert flask_app.template_folder == 'templates'
  ```

- [ ] **Step 2: Run new tests to verify they fail**

  ```bash
  pytest tests/test_web_app_waitress.py::test_create_app_uses_bundle_paths_when_frozen \
         tests/test_web_app_waitress.py::test_create_app_uses_normal_paths_when_not_frozen -v
  ```

  Expected: FAIL — `create_app()` does not check `sys.frozen`.

- [ ] **Step 3: Update create_app() in app/web/app.py**

  Replace the current `create_app` opening:

  ```python
  def create_app(config_path, skip_validation=False):
      app = Flask(__name__)
  ```

  with:

  ```python
  def create_app(config_path, skip_validation=False):
      if getattr(sys, 'frozen', False):
          # Running as a PyInstaller bundle.
          # --onedir: resources are next to the executable
          # --onefile: resources are in sys._MEIPASS (temp dir)
          bundle_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
          app = Flask(
              __name__,
              template_folder=os.path.join(bundle_dir, 'app', 'web', 'templates'),
              static_folder=os.path.join(bundle_dir, 'app', 'web', 'static'),
          )
      else:
          app = Flask(__name__)
  ```

  Note: `sys` is now imported at module level (added in Task 2). `os` was already imported at the top of the file.

- [ ] **Step 4: Run the new tests to verify they pass**

  ```bash
  pytest tests/test_web_app_waitress.py -v
  ```

  Expected: all 4 tests pass

- [ ] **Step 5: Run full test suite to check for regressions**

  ```bash
  pytest
  ```

  Expected: same pass/fail count as before

- [ ] **Step 6: Commit**

  ```bash
  git add app/web/app.py tests/test_web_app_waitress.py
  git commit -m "feat: resolve template/static paths from PyInstaller bundle dir"
  ```

---

## Chunk 2: Installer Files

### Task 4: Create PyInstaller entry point and spec file

**Files:**
- Create: `installer/main_win.py`
- Create: `installer/dq_workbench.spec`

PyInstaller requires a top-level script as its entry point. We use a thin shim so `app/web/app.py` stays clean.

- [ ] **Step 1: Create installer/ directory and entry point**

  ```bash
  mkdir -p installer
  ```

  Create `installer/main_win.py`:

  ```python
  # installer/main_win.py
  # PyInstaller entry point for the Windows desktop app.
  from app.web.app import main

  if __name__ == '__main__':
      main()
  ```

- [ ] **Step 2: Verify the entry point works**

  From the project root:

  ```bash
  python installer/main_win.py --help
  ```

  Expected: prints the argparse help message and exits (no errors).

- [ ] **Step 3: Create installer/dq_workbench.spec**

  ```python
  # installer/dq_workbench.spec
  # -*- mode: python ; coding: utf-8 -*-

  block_cipher = None

  a = Analysis(
      ['main_win.py'],
      pathex=['..'],          # project root — so 'app.web.app' resolves correctly
      binaries=[],
      datas=[
          ('../app/web/templates', 'app/web/templates'),
          ('../app/web/static',    'app/web/static'),
      ],
      hiddenimports=[
          'waitress',
          'waitress.utilities',
          'flask_wtf',
          'pkg_resources',
          'pkg_resources.extern',
      ],
      hookspath=[],
      hooksconfig={},
      runtime_hooks=[],
      excludes=['gunicorn'],  # gunicorn is Linux-only; exclude from the Windows bundle
      win_no_prefer_redirects=False,
      win_private_assemblies=False,
      cipher=block_cipher,
      noarchive=False,
  )

  pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

  exe = EXE(
      pyz,
      a.scripts,
      [],
      exclude_binaries=True,
      name='dq-workbench',
      debug=False,
      bootloader_ignore_signals=False,
      strip=False,
      upx=True,
      console=True,           # Keep console window — closing it stops the server
      disable_windowed_traceback=False,
      argv_emulation=False,
      target_arch=None,
      codesign_identity=None,
      entitlements_file=None,
  )

  coll = COLLECT(
      exe,
      a.binaries,
      a.zipfiles,
      a.datas,
      strip=False,
      upx=True,
      upx_exclude=[],
      name='dq-workbench',
  )
  ```

- [ ] **Step 4: Verify the spec file is valid Python**

  ```bash
  python -c "
  import ast, sys
  with open('installer/dq_workbench.spec') as f:
      src = f.read()
  ast.parse(src)
  print('spec syntax ok')
  "
  ```

  Expected: `spec syntax ok`

- [ ] **Step 5: Commit**

  ```bash
  git add installer/main_win.py installer/dq_workbench.spec
  git commit -m "feat: add PyInstaller entry point and spec file"
  ```

---

### Task 5: Create Inno Setup script

**Files:**
- Create: `installer/dq_workbench_win.iss`

Inno Setup reads this script to produce the `.exe` installer. `AppVersion` is passed at build time with `/DAppVersion=X.Y.Z`.

- [ ] **Step 1: Create installer/dq_workbench_win.iss**

  ```ini
  ; installer/dq_workbench_win.iss
  ; Inno Setup 6 script for DQ Workbench
  ; Build with: ISCC.exe /DAppVersion=0.9.4 dq_workbench_win.iss

  [Setup]
  AppName=DQ Workbench
  AppVersion={#AppVersion}
  AppPublisher=DHIS2
  DefaultDirName={autopf}\DQ Workbench
  DefaultGroupName=DQ Workbench
  OutputBaseFilename=dq-workbench-{#AppVersion}-windows-setup
  OutputDir=Output
  Compression=lzma
  SolidCompression=yes
  ; Installer requires Windows 10 or later
  MinVersion=10.0

  [Languages]
  Name: "english"; MessagesFile: "compiler:Default.isl"

  [Files]
  ; Bundle all files from the PyInstaller --onedir output
  Source: "..\dist\dq-workbench\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

  [Icons]
  ; Start Menu shortcuts
  Name: "{group}\DQ Workbench";  Filename: "{app}\dq-workbench.exe"
  Name: "{group}\Uninstall DQ Workbench"; Filename: "{uninstallexe}"
  ; Optional desktop shortcut (user opts in via checkbox during install)
  Name: "{commondesktop}\DQ Workbench"; Filename: "{app}\dq-workbench.exe"; Tasks: desktopicon

  [Tasks]
  Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

  [Run]
  ; Offer to launch the app at the end of the install wizard
  Filename: "{app}\dq-workbench.exe"; Description: "Launch DQ Workbench now"; Flags: postinstall nowait skipifsilent
  ```

- [ ] **Step 2: Verify the .iss file is well-formed**

  The ISS format cannot be validated without Inno Setup itself (Windows-only). Instead, verify it is valid UTF-8 text with expected section headers:

  ```bash
  python -c "
  import re
  with open('installer/dq_workbench_win.iss', encoding='utf-8') as f:
      content = f.read()
  required = ['[Setup]', '[Files]', '[Icons]', '[Tasks]', '[Run]']
  for section in required:
      assert section in content, f'Missing section: {section}'
  print('ISS structure ok')
  "
  ```

  Expected: `ISS structure ok`

- [ ] **Step 3: Commit**

  ```bash
  git add installer/dq_workbench_win.iss
  git commit -m "feat: add Inno Setup installer script"
  ```

---

### Task 6: Create GitHub Actions workflow

**Files:**
- Create: `.github/workflows/windows-installer.yml`

Triggered on every `v*` tag push (same pattern as the existing `docker-publish.yml`). Runs on `windows-latest`, which has Inno Setup 6 pre-installed.

- [ ] **Step 1: Create .github/workflows/windows-installer.yml**

  ```yaml
  # .github/workflows/windows-installer.yml
  name: Build Windows installer

  on:
    push:
      tags:
        - 'v*'

  jobs:
    build:
      runs-on: windows-latest

      steps:
        - name: Checkout
          uses: actions/checkout@v4

        - name: Set up Python
          uses: actions/setup-python@v5
          with:
            python-version: '3.11'

        - name: Install dependencies
          run: pip install -e .[dev] pyinstaller

        - name: Build with PyInstaller
          working-directory: installer
          run: pyinstaller dq_workbench.spec

        - name: Build installer with Inno Setup
          run: |
            $version = "${{ github.ref_name }}".TrimStart("v")
            & "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" `
              /DAppVersion=$version `
              installer\dq_workbench_win.iss

        - name: Upload to GitHub Release
          uses: softprops/action-gh-release@v2
          with:
            files: installer/Output/dq-workbench-*-windows-setup.exe
  ```

- [ ] **Step 2: Verify the YAML is valid**

  ```bash
  python -c "
  import yaml
  with open('.github/workflows/windows-installer.yml') as f:
      data = yaml.safe_load(f)
  assert data['on']['push']['tags'] == ['v*']
  assert data['jobs']['build']['runs-on'] == 'windows-latest'
  print('workflow YAML ok')
  "
  ```

  Expected: `workflow YAML ok`

- [ ] **Step 3: Run the full test suite one final time**

  ```bash
  pytest
  ```

  Expected: same pass/fail count as before (pre-existing `test_values_boxcox_with_zero` failure is unrelated)

- [ ] **Step 4: Commit**

  ```bash
  git add .github/workflows/windows-installer.yml
  git commit -m "feat: add GitHub Actions workflow to build Windows installer"
  ```

---

## Local Build Verification (Manual, Windows only)

After the above tasks are complete, verify the full installer locally on a Windows machine or GitHub Actions:

```powershell
# From the project root (Windows PowerShell)
pip install -e .[dev] pyinstaller
cd installer
pyinstaller dq_workbench.spec
cd ..
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DAppVersion=0.9.4 installer\dq_workbench_win.iss
# Output: installer\Output\dq-workbench-0.9.4-windows-setup.exe
```

Run the installer and verify:
1. Wizard completes without error
2. Start Menu shortcut appears
3. Double-clicking the shortcut opens a console window
4. Browser opens to `http://127.0.0.1:5000`
5. First-run redirects to the server config page
6. Config created at `C:\Users\<name>\Documents\DQ Workbench\config.yml`
7. Closing the console window stops the server