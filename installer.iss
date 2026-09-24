; ============================================================
; AccessibleIDE - Windows Setup (Inno Setup)
; Installs the app to a directory of the user's choice,
; installs Python and adds it to PATH, installs the
; Microsoft Visual C++ runtime, and creates shortcuts.
; ============================================================

#define MyAppName "AccessibleIDE"
#define MyAppVersion "0.2.1"
#define MyAppExeName "AccessibleIDE.exe"
#define MyAppPublisher "AccessibleIDE"
#define MyAppURL "https://accessible-coding.onrender.com"

[Setup]
AppId={{8E5F2C1A-9B3D-4E7A-8C2F-1D4B6A9E3F50}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\AccessibleIDE
DefaultGroupName=AccessibleIDE
DisableProgramGroupPage=yes
OutputDir=installer
OutputBaseFilename=AccessibleIDE-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
MinVersion=10.0
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"
Name: "installpython"; Description: "Install Python and add it to PATH"; GroupDescription: "Python:"; Flags: checkedonce

[Files]
Source: "dist\AccessibleIDE\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "installer\prereqs\vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall
Source: "installer\prereqs\python-3.13.15-amd64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: ShouldInstallPython

[Run]
Filename: "{tmp}\vc_redist.x64.exe"; Parameters: "/install /quiet /norestart"; StatusMsg: "Installing Microsoft Visual C++ Runtime..."; Flags: waituntilterminated
Filename: "{tmp}\python-3.13.15-amd64.exe"; Parameters: "/quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_doc=0 Include_launcher=0 Shortcuts=0"; StatusMsg: "Installing Python and adding it to PATH..."; Flags: waituntilterminated; Check: ShouldInstallPython
Filename: "{app}\{#MyAppExeName}"; Description: "Launch AccessibleIDE"; Flags: nowait postinstall skipifsilent

[Icons]
Name: "{group}\AccessibleIDE"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall AccessibleIDE"; Filename: "{uninstallexe}"
Name: "{autodesktop}\AccessibleIDE"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Code]
{ Returns True if a usable Python (3.10+) is already installed. }
function IsPythonInstalled: Boolean;
var
  Version: String;
begin
  Result := False;
  if RegQueryStringValue(HKCU, 'Software\Python\PythonCore\3.10\InstallPath', '', Version) then Result := True;
  if RegQueryStringValue(HKCU, 'Software\Python\PythonCore\3.11\InstallPath', '', Version) then Result := True;
  if RegQueryStringValue(HKCU, 'Software\Python\PythonCore\3.12\InstallPath', '', Version) then Result := True;
  if RegQueryStringValue(HKCU, 'Software\Python\PythonCore\3.13\InstallPath', '', Version) then Result := True;
  if RegQueryStringValue(HKCU, 'Software\Python\PythonCore\3.14\InstallPath', '', Version) then Result := True;
  if RegQueryStringValue(HKLM, 'Software\Python\PythonCore\3.10\InstallPath', '', Version) then Result := True;
  if RegQueryStringValue(HKLM, 'Software\Python\PythonCore\3.11\InstallPath', '', Version) then Result := True;
  if RegQueryStringValue(HKLM, 'Software\Python\PythonCore\3.12\InstallPath', '', Version) then Result := True;
  if RegQueryStringValue(HKLM, 'Software\Python\PythonCore\3.13\InstallPath', '', Version) then Result := True;
  if RegQueryStringValue(HKLM, 'Software\Python\PythonCore\3.14\InstallPath', '', Version) then Result := True;
end;

{ Install Python only if the task is selected AND no Python is present. }
function ShouldInstallPython: Boolean;
begin
  Result := WizardIsTaskSelected('installpython') and not IsPythonInstalled;
end;