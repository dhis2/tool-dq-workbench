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
