; Installatore Windows di Deal Combined (Inno Setup 6, gratuito: https://jrsoftware.org/isinfo.php)
;
; Prima compila l'eseguibile:   pyinstaller gestionale.spec --noconfirm
; poi l'installatore:           "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\DealCombined.iss
; oppure fai tutto con:         build_windows.bat
;
; Risultato: dist\Installa-DealCombined.exe
; I dati NON stanno nella cartella del programma ma in Documenti\Deal Combined
; (o nella cartella scelta in Impostazioni → Dati e backup): disinstallare il
; programma non cancella mai clienti, polizze e documenti.

#define NomeApp "Deal Combined"
#define VersioneApp "2.0.0"
#define Eseguibile "DealCombined.exe"

[Setup]
AppId={{B6C2D1F0-5D0A-4C8E-9C1E-7A2E4F3D9B11}
AppName={#NomeApp}
AppVersion={#VersioneApp}
AppPublisher={#NomeApp}
DefaultDirName={autopf}\{#NomeApp}
DefaultGroupName={#NomeApp}
DisableProgramGroupPage=yes
; Installazione per il solo utente: niente richiesta di permessi da amministratore.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=Installa-DealCombined
SetupIconFile=deal-combined.ico
UninstallDisplayIcon={app}\{#Eseguibile}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktopicon"; Description: "Crea un'icona sul desktop"; GroupDescription: "Icone:"

[Files]
Source: "..\dist\{#Eseguibile}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#NomeApp}"; Filename: "{app}\{#Eseguibile}"
Name: "{group}\Disinstalla {#NomeApp}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#NomeApp}"; Filename: "{app}\{#Eseguibile}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#Eseguibile}"; Description: "Avvia {#NomeApp}"; Flags: nowait postinstall skipifsilent
