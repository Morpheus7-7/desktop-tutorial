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
; La versione si può passare da riga di comando: ISCC /DVersioneApp=2.1.0 …
#ifndef VersioneApp
  #define VersioneApp "2.1.0"
#endif
#define Eseguibile "DealCombined.exe"

[Setup]
AppId={{B6C2D1F0-5D0A-4C8E-9C1E-7A2E4F3D9B11}
AppName={#NomeApp}
AppVersion={#VersioneApp}
VersionInfoVersion={#VersioneApp}
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
Name: "avvioautomatico"; Description: "Avvia con Windows (icona vicino all'orologio con i promemoria)"; GroupDescription: "Promemoria:"

[Files]
Source: "..\dist\{#Eseguibile}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#NomeApp}"; Filename: "{app}\{#Eseguibile}"
Name: "{group}\Disinstalla {#NomeApp}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#NomeApp}"; Filename: "{app}\{#Eseguibile}"; Tasks: desktopicon

[Registry]
; Stesso nome e parametro usati da Impostazioni → Programma (gestionale/promemoria.py).
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#NomeApp}"; ValueData: """{app}\{#Eseguibile}"" --avvio-silenzioso"; Flags: uninsdeletevalue; Tasks: avvioautomatico
; Se l'avvio con Windows è stato attivato dal programma, la disinstallazione lo toglie comunque.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "{#NomeApp}"; Flags: uninsdeletevalue dontcreatekey

[Run]
Filename: "{app}\{#Eseguibile}"; Description: "Avvia {#NomeApp}"; Flags: nowait postinstall skipifsilent
; Aggiornamento automatico (installazione silenziosa): riapre il programma.
Filename: "{app}\{#Eseguibile}"; Flags: nowait; Check: WizardSilent

[Code]
// Durante un aggiornamento il vecchio DealCombined.exe potrebbe essere
// ancora in chiusura: si aspetta qualche secondo che il file si liberi.
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Tentativi: Integer;
  Percorso: String;
begin
  Result := '';
  Percorso := ExpandConstant('{app}\{#Eseguibile}');
  Tentativi := 0;
  while FileExists(Percorso) and (not RenameFile(Percorso, Percorso + '.vecchio')) and (Tentativi < 20) do
  begin
    Sleep(500);
    Tentativi := Tentativi + 1;
  end;
  if FileExists(Percorso + '.vecchio') then
  begin
    if not RenameFile(Percorso + '.vecchio', Percorso) then
      DeleteFile(Percorso + '.vecchio');
  end;
end;
