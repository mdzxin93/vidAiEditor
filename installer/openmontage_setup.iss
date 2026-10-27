; OpenMontage Windows Installer Script (Inno Setup 6)
; Phase 12: Production Packaging and Release Engineering

#define MyAppName "OpenMontage AI Video Editor"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "OpenMontage Authors"
#define MyAppURL "https://github.com/mdzxin93/RawEdites-"
#define MyAppExeName "OpenMontage.bat"

[Setup]
AppId={{5A8D3899-23B7-4D90-95B6-D441AE251BC2}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={userpf}\OpenMontage
DisableProgramGroupPage=yes
; Per-user installation: Does NOT require Administrator privileges!
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=OpenMontage-Setup-v{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Distribute all source, backend, frontend dist, and scripts
Source: "..\OpenMontage.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\OpenMontage-Silent.vbs"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\backlot\*"; DestDir: "{app}\backlot"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\lib\*"; DestDir: "{app}\lib"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\tools\*"; DestDir: "{app}\tools"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\pipeline_defs\*"; DestDir: "{app}\pipeline_defs"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\frontend\dist\*"; DestDir: "{app}\frontend\dist"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\remotion-composer\*"; DestDir: "{app}\remotion-composer"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "node_modules\.cache"
Source: "..\scripts\launcher.py"; DestDir: "{app}\scripts"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion

; NOTE: User projects in %LOCALAPPDATA%\OpenMontage\projects are NEVER overwritten or deleted!

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\OpenMontage.bat"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\OpenMontage.bat"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Filename: "{app}\OpenMontage.bat"; Flags: nowait postinstall skipifsilent
