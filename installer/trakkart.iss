; TRAKKART installer (Inno Setup 6).
; Version comes from the command line: ISCC /DMyVersion=1.6.0 installer/trakkart.iss
; (build_installer.py does this automatically from app.__version__).
; Expects the one-dir build in dist/portable/TRAKKART (python build_portable.py).

#ifndef MyVersion
  #define MyVersion "1.6.0"
#endif

[Setup]
AppName=TRAKKART
AppVersion={#MyVersion}
AppVerName=TRAKKART {#MyVersion}
AppPublisher=ShardBeats
AppPublisherURL=https://github.com/shardbeats/TRAKKART
DefaultDirName={autopf}\TRAKKART
DefaultGroupName=TRAKKART
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE
OutputDir=..\dist-installer
OutputBaseFilename=TRAKKART-Setup-{#MyVersion}
Compression=lzma2/max
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
UninstallDisplayName=TRAKKART {#MyVersion}
; Portable data stays per-user, nothing is written to the install folder.

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\portable\TRAKKART\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\TRAKKART"; Filename: "{app}\TRAKKART.exe"
Name: "{group}\User manual"; Filename: "{app}\MANUAL.md"
Name: "{autodesktop}\TRAKKART"; Filename: "{app}\TRAKKART.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\TRAKKART.exe"; Description: "{cm:LaunchProgram,TRAKKART}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Installed files only; per-user data (prefs/db/logs) is left behind on purpose.
Type: files; Name: "{app}\MANUAL.md"
