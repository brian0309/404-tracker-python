; Inno Setup script for scanner404
; Values are injected by build.bat via /D defines.

#ifndef AppName
#define AppName "Scanner404"
#endif

#ifndef AppVersion
#define AppVersion "1.0.0"
#endif

#ifndef Publisher
#define Publisher "Scanner404"
#endif

#ifndef SourceDir
#define SourceDir "build\\main.dist"
#endif

#ifndef OutputDir
#define OutputDir "build\\installer"
#endif

#ifndef OutputBaseFilename
#define OutputBaseFilename "scanner404-setup"
#endif

[Setup]
AppId={{B0E87F65-834E-4A0E-9F89-0B9ED7CE7444}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#Publisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputDir={#OutputDir}
OutputBaseFilename={#OutputBaseFilename}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "{#SourceDir}\\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\scanner404.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\scanner404.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\scanner404.exe"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
