# PyInstaller spec — Deal Combined (eseguibile «one-file»)
#
# Costruzione:
#     pip install -r requirements-build.txt
#     pyinstaller gestionale.spec --noconfirm
#
# L'eseguibile risultante è in  dist/  (DealCombined.exe su Windows); l'installatore
# si crea poi con installer/DealCombined.iss (vedi build_windows.bat).
# Vedi PACKAGING.md per i dettagli.

block_cipher = None

# Template Jinja e file statici: inclusi mantenendo la struttura del pacchetto.
datas = [
    ("gestionale/templates", "gestionale/templates"),
    ("gestionale/static", "gestionale/static"),
]

# I blueprint delle route sono importati dinamicamente dentro
# register_blueprints(): li dichiariamo esplicitamente. Per Flask e SQLAlchemy
# provvedono gli hook integrati di PyInstaller.
hiddenimports = [
    "gestionale.routes.audit",
    "gestionale.routes.auth",
    "gestionale.routes.claims",
    "gestionale.routes.clients",
    "gestionale.routes.documents",
    "gestionale.routes.followups",
    "gestionale.routes.main",
    "gestionale.routes.notifications",
    "gestionale.routes.opportunities",
    "gestionale.routes.policies",
    "gestionale.routes.settings",
    "gestionale.routes.sincronizzazione",
    "gestionale.routes.titles",
    "gestionale.routes.users",
    "gestionale.cli",
    "gestionale.routes.academy",
    "gestionale.routes.client_sheets",
    "gestionale.routes.privacy",
    "gestionale.routes.importazione",
    "gestionale.routes.note",
    "gestionale.tray",
    "pystray._win32",
    "PIL.Image",
    "PIL.ImageDraw",
    "openpyxl",
    "reportlab",
    "flask_sqlalchemy",
    "sqlalchemy.dialects.sqlite",
    "waitress",
    # Finestra propria del programma (WebView2 su Windows).
    "webview",
    "webview.platforms.edgechromium",
    "webview.platforms.winforms",
]

a = Analysis(
    ["run_desktop.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # L'app usa solo ssl/smtplib della stdlib: il pacchetto cryptography non
    # serve. Escluderlo alleggerisce il bundle ed evita hook superflui.
    excludes=["tkinter", "cryptography"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Schermata di caricamento mostrata subito al doppio clic, mentre l'exe si
# prepara (i primi secondi, soprattutto al primo avvio o con l'antivirus).
# Richiede Tcl/Tk nel Python usato per la build (incluso nell'installer di
# python.org); se non disponibile, l'exe si crea lo stesso senza.
import importlib.util

splash = None
try:
    if importlib.util.find_spec("_tkinter") is None:
        raise RuntimeError("Tcl/Tk non installato nel Python di build")
    splash = Splash(
        "packaging/splash.png",
        binaries=a.binaries,
        datas=a.datas,
        text_pos=(20, 215),
        text_size=10,
        text_color="#e8f0ea",
        text_default="Avvio in corso…",
        minify_script=True,
        always_on_top=False,
    )
except (Exception, SystemExit) as errore:  # noqa: BLE001 - PyInstaller segnala con SystemExit
    splash = None
    print(f"Schermata di avvio non disponibile: {errore}")

exe = EXE(
    pyz,
    a.scripts,
    *([splash, splash.binaries] if splash else []),
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="DealCombined",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # finestra propria (pywebview); i messaggi vanno in deal-combined.log
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="installer/deal-combined.ico",
)
