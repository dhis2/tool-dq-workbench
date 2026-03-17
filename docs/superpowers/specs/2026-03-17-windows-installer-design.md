
# Design: Windows Installer (PyInstaller + Inno Setup)

**Date:** 2026-03-17
**Status:** Approved

## Overview

Package the DQ Workbench web UI as a standard Windows installer (`.exe`) for non-technical users who are responsible for creating the DHIS2 configuration file and handing it to a sysadmin. The installer must work with no command-line interaction: double-click to install, double-click the shortcut to run.

The zero-config startup feature (already implemented) is a prerequisite — it handles first-run config creation and redirects the user to the server setup page automatically.

## Approach

PyInstaller `--onedir` bundles the Flask app and all dependencies into a directory. Inno Setup wraps that directory into a standard Windows installer wizard. GitHub Actions builds the installer automatically on every version tag using a `windows-latest` runner.

**Not included in scope:**
- Code signing (trusted user base; SmartScreen "More info → Run anyway" is acceptable)
- Auto-update (users download and re-run the installer for new versions)
- System tray icon (console window is sufficient; closing it stops the server)

## Runtime User Experience

1. User downloads `dq-workbench-X.Y.Z-windows-setup.exe` from GitHub Releases
2. Runs the installer wizard (Next → Next → Install); SmartScreen warns — user clicks "More info → Run anyway"
3. Double-clicks the Start Menu or desktop shortcut
4. A console window opens; `waitress` starts serving on `http://127.0.0.1:5000`; browser opens automatically
5. First run: redirected to the server config page to enter DHIS2 credentials; config created at `C:\Users\<name>\Documents\DQ Workbench\config.yml`
6. Subsequent runs: dashboard loads directly
7. User closes the console window to stop the server

## Python Changes

### `pyproject.toml`

Add `waitress` as a runtime dependency. Add a platform marker to `gunicorn` so it is not installed on Windows (gunicorn is Linux/macOS only):

```toml
"gunicorn>=23,<25; sys_platform != 'win32'",
"waitress>=3.0,<4",
```

### `app/web/app.py`

**Replace `app.run()` with waitress in `main()`:**

```python
import threading
import webbrowser
from waitress import serve

# Open browser after waitress has had time to bind the port
threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:5000")).start()

print("=" * 60)
print("DQ Workbench is running at http://127.0.0.1:5000")
print("Close this window to stop the server.")
print("=" * 60)
serve(app, host="127.0.0.1", port=5000)
```

`webbrowser.open` is cross-platform; this path is used on Linux too (replacing Flask's dev server, which is equivalent from the user's perspective). The `--debug` flag prints extra info but still uses waitress.

**Add `sys._MEIPASS` path resolution in `create_app()`:**

When running as a PyInstaller bundle, Flask cannot find templates and static files at their normal paths. Resolve them via `sys._MEIPASS` (the temp directory PyInstaller extracts to):

```python
import sys
import os

base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
app = Flask(
    __name__,
    template_folder=os.path.join(base, 'app', 'web', 'templates'),
    static_folder=os.path.join(base, 'app', 'web', 'static'),
)
```

When not running as a bundle, `sys._MEIPASS` does not exist and `getattr` falls back to the normal package directory — so development and Docker are unaffected.

## New Files

### `installer/main_win.py`

A clean PyInstaller entry point that calls `main()`:

```python
from app.web.app import main

if __name__ == '__main__':
    main()
```

PyInstaller requires a single top-level script as its entry point. Using a separate file avoids polluting `app/web/app.py` with PyInstaller-specific concerns.

### `installer/dq_workbench.spec`

PyInstaller spec file declaring all assets and hidden imports:

```python
a = Analysis(
    ['main_win.py'],
    pathex=['..'],
    hiddenimports=[
        'waitress',
        'flask_wtf',
        'pkg_resources',
    ],
    datas=[
        ('../app/web/templates', 'app/web/templates'),
        ('../app/web/static',    'app/web/static'),
    ],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, name='dq-workbench', console=True)
coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, name='dq-workbench')
```

`console=True` keeps the terminal window visible. `datas` maps templates and static files into the bundle at paths matching what `sys._MEIPASS` resolution expects. Hidden imports cover dynamically-loaded modules that PyInstaller's static analysis misses.

### `installer/dq_workbench_win.iss`

Inno Setup script:

```ini
[Setup]
AppName=DQ Workbench
AppVersion={#AppVersion}
DefaultDirName={autopf}\DQ Workbench
DefaultGroupName=DQ Workbench
OutputBaseFilename=dq-workbench-{#AppVersion}-windows-setup
OutputDir=Output
Compression=lzma
SolidCompression=yes

[Files]
Source: "..\dist\dq-workbench\*"; DestDir: "{app}"; Flags: recursesubdirs

[Icons]
Name: "{group}\DQ Workbench";        Filename: "{app}\dq-workbench.exe"
Name: "{group}\Uninstall";           Filename: "{uninstallexe}"
Name: "{commondesktop}\DQ Workbench"; Filename: "{app}\dq-workbench.exe"; Tasks: desktopicon

[Tasks]
Name: desktopicon; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\dq-workbench.exe"; Description: "Launch DQ Workbench"; Flags: postinstall nowait skipifsilent
```

`AppVersion` is passed at build time via `/DAppVersion=X.Y.Z`. Output: `installer/Output/dq-workbench-X.Y.Z-windows-setup.exe`.

### `.github/workflows/windows-installer.yml`

Triggered on every `v*` tag push, in parallel with the existing Docker workflow:

```yaml
name: Build Windows installer

on:
  push:
    tags:
      - 'v*'

jobs:
  build:
    runs-on: windows-latest

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
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

`windows-latest` runners have Inno Setup 6 pre-installed. The version is extracted from the git tag (`v0.9.4` → `0.9.4`). The `.exe` is attached to the GitHub Release alongside the Docker image.

## What Is Not Changing

- `create_app_from_env()` and the Docker/gunicorn production path — untouched
- `CONFIG_PATH` environment variable (Docker-only) — unchanged
- Linux/macOS command-line usage — waitress is cross-platform; behaviour is identical to today
- The `--config`, `--skip-validation`, `--debug` flags — unchanged
- Zero-config startup logic — already implemented; config path on Windows is already `~/Documents/DQ Workbench/config.yml`
