#define AppVersion "0.2.0"
#define AppName "Credential Studio"

[Setup]
AppId={{4C05E311-58B7-4D55-965D-2D7D89E9B73A}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Credential Studio
AppSupportURL=https://github.com/birleopold/ID-Issuance-System-/issues
DefaultDirName={localappdata}\Programs\CredentialStudio
DefaultGroupName={#AppName}
UninstallDisplayIcon={app}\CredentialStudio.exe
OutputDir=..\dist\installer
OutputBaseFilename=CredentialStudio-{#AppVersion}-Setup-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
CloseApplications=yes
RestartApplications=no
SetupLogging=yes

[Files]
Source: "..\dist\CredentialStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\CredentialStudio.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\CredentialStudio.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\CredentialStudio.exe"; Description: "Launch Credential Studio"; Flags: nowait postinstall skipifsilent

; User data lives outside {app}. Uninstall intentionally preserves it.
