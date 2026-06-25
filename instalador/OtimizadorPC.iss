; ============================================================================
;  Otimizador PC - script do instalador (Inno Setup 6+).
;
;  Gera "OtimizadorPC-Setup.exe": um instalador profissional com atalhos no
;  Menu Iniciar (e, opcionalmente, na Area de Trabalho), icone proprio,
;  desinstalador e suporte a portugues/ingles.
;
;  Os dados gravaveis (logs, backups, preferencias) ficam em
;  %LOCALAPPDATA%\OtimizadorPC (o programa cuida disso) - por isso instalar em
;  "Program Files" e' seguro, sem quebrar backups nem o "desfazer".
;
;  Compilar (no Windows, com o .exe ja em ..\dist):
;      ISCC.exe /DMyAppVersion=2.2.0 instalador\OtimizadorPC.iss
;  (se MyAppVersion nao for passado, usa o valor padrao abaixo)
; ============================================================================

#ifndef MyAppVersion
  #define MyAppVersion "2.2.0"
#endif
#define MyAppName "Otimizador PC"
#define MyAppExeName "OtimizadorPC.exe"
#define MyAppPublisher "Caionickpi"
#define MyAppURL "https://github.com/Caionickpi/otimizador-pc"

[Setup]
; AppId identifica o programa para atualizacoes/desinstalacao - NAO mudar.
AppId={{8F2A6C31-5B7D-4E9A-9C21-7A3D2E5F1B40}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\Otimizador PC
DefaultGroupName=Otimizador PC
DisableProgramGroupPage=yes
DisableReadyPage=no
AllowNoIcons=yes
OutputDir=..\dist
OutputBaseFilename=OtimizadorPC-Setup
SetupIconFile=..\dados\icone.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
ArchitecturesAllowed=x64
PrivilegesRequired=admin
MinVersion=10.0

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
{ Ao desinstalar, oferece remover tambem os dados do usuario (logs/backups/preferencias). }
procedure CurUninstallStepChanged(CurStep: TUninstallStep);
var
  Dados: String;
begin
  if CurStep = usPostUninstall then
  begin
    if UninstallSilent then
      exit;
    Dados := ExpandConstant('{localappdata}\OtimizadorPC');
    if DirExists(Dados) then
    begin
      if MsgBox('Remover tambem os dados do Otimizador PC (logs, backups e preferencias)?'
        + #13#10 + Dados, mbConfirmation, MB_YESNO) = IDYES then
        DelTree(Dados, True, True, True);
    end;
  end;
end;
