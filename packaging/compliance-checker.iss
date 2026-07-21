; Inno Setup script — wraps the PyInstaller-built compliance-checker.exe
; into a real Windows installer with Start Menu shortcuts and a proper
; uninstaller registered in Settings > Apps / Control Panel.
;
; Requires Inno Setup (free): https://jrsoftware.org/isinfo.php
;
; Build order:
;   1. npm run build              (frontend/dist)
;   2. pyinstaller packaging\compliance-checker.spec   (dist\compliance-checker.exe)
;   3. Compile this script in the Inno Setup Compiler (or `iscc` on the CLI)
;
; Produces installer_output\ComplianceChecker-Setup.exe

#define MyAppName "Compliance Checker"
#define MyAppVersion "0.1.0"
#define MyAppExeName "compliance-checker.exe"

[Setup]
AppId={{B7B6C8B0-6C6E-4B0A-9B0D-COMPLIANCECHK1}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
; Per-user install under %LOCALAPPDATA% — no admin rights / UAC prompt needed.
DefaultDirName={localappdata}\Programs\ComplianceChecker
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputDir=installer_output
OutputBaseFilename=ComplianceChecker-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

; Deliberately NOT deleting %APPDATA%\ComplianceChecker on uninstall — that
; folder holds the compliance database and the encryption key for stored
; credential-profile passwords. Standard Windows convention is to leave
; user data behind on uninstall in case of reinstall; the packaging README
; tells Steve (or whoever's tidying up) where to find it if a full wipe is
; ever wanted.
