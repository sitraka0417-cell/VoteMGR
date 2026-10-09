; ============================================================
; votemgr.iss — Script Inno Setup pour VoteMGR
;
; Prérequis :
;   1) Avoir déjà compilé l'application avec installer\build.bat
;      (le dossier dist\VoteMGR\ doit exister, avec VoteMGR.exe dedans)
;   2) Installer Inno Setup : https://jrsoftware.org/isinfo.php
;
; Utilisation :
;   - Ouvrir ce fichier avec "Inno Setup Compiler" et cliquer "Compile"
;   - OU en ligne de commande :  ISCC.exe installer\votemgr.iss
;
; Résultat : installer\Output\VoteMGR-Setup.exe
; ============================================================

#define MyAppName "VoteMGR"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Sitraka Nambinintsoa"
#define MyAppExeName "VoteMGR.exe"

[Setup]
AppId={{B7B6A6D2-9C2A-4E6A-9B2A-5E1C7B7A9A11}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=VoteMGR-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
; L'application ouvre une fenêtre en plein écran sur le 2e moniteur :
; on ne force pas de droits admin particuliers.
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer une icône sur le Bureau"; GroupDescription: "Icônes supplémentaires :"

[Files]
; Copie tout le contenu généré par PyInstaller (dist\VoteMGR\*)
Source: "..\dist\VoteMGR\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Désinstaller {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Lancer {#MyAppName}"; Flags: nowait postinstall skipifsilent
