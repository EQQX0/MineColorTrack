; Inno Setup script: wraps the PyInstaller output into one MineColorTrack-Setup-<version>.exe
; Build: ISCC.exe /DMyAppVersion=1.0.0 packaging\MineColorTrack.iss   (after PyInstaller)

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#define MyAppName "MineColorTrack"
#define MyAppExe "MineColorTrack.exe"

[Setup]
AppId={{8C2B6E1A-4F7D-4B4B-9A51-6C0E2D9B7F31}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=EQQX0
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=MineColorTrack-Setup-{#MyAppVersion}
SetupIconFile=..\colorassist\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExe}
UninstallDisplayName={#MyAppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
; The app holds this mutex while running, so Setup and the uninstaller ask you to close it first.
AppMutex=MineColorTrackRunning
ChangesEnvironment=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "addtopath"; Description: "Add the mct command-line tool to PATH (for scripts and AI agents)"; GroupDescription: "Command line:"

[Files]
Source: "..\dist\MineColorTrack\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; 1.0.x put a single shortcut directly in the Start menu; it now lives in a MineColorTrack folder.
Type: files; Name: "{autoprograms}\{#MyAppName}.lnk"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"; Comment: "Remove {#MyAppName} from this PC"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Tasks: addtopath; Check: NotInPath(ExpandConstant('{app}'))

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[Code]
function NotInPath(Dir: String): Boolean;
var
  Current: String;
begin
  if not RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', Current) then
    Current := '';
  Result := Pos(';' + Uppercase(Dir) + ';', ';' + Uppercase(Current) + ';') = 0;
end;

// Take our folder out of the user's PATH again on uninstall.
procedure RemoveFromPath(Dir: String);
var
  Current: String;
  P: Integer;
begin
  if not RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', Current) then
    exit;
  Current := ';' + Current + ';';
  P := Pos(';' + Uppercase(Dir) + ';', Uppercase(Current));
  if P > 0 then
  begin
    Delete(Current, P, Length(Dir) + 1);
    Current := Copy(Current, 2, Length(Current) - 2);
    RegWriteExpandStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', Current);
  end;
end;

// After the program files are removed, offer to delete the user's settings and profiles too.
// Silent uninstalls (/SUPPRESSMSGBOXES) keep them.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  SettingsDir: String;
begin
  if CurUninstallStep = usUninstall then
    RemoveFromPath(ExpandConstant('{app}'));
  if CurUninstallStep = usPostUninstall then
  begin
    SettingsDir := ExpandConstant('{userappdata}\{#MyAppName}');
    if DirExists(SettingsDir) then
      if SuppressibleMsgBox('Also delete your {#MyAppName} settings and profiles?' + #13#10#13#10 +
                            'Choose No to keep them for a later reinstall.' + #13#10#13#10 + SettingsDir,
                            mbConfirmation, MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES then
        DelTree(SettingsDir, True, True, True);
  end;
end;
