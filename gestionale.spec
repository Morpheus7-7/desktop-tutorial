# PyInstaller spec — Gestionale Assicurativo (eseguibile «one-file»)
#
# Costruzione:
#     pip install -r requirements-build.txt
#     pyinstaller gestionale.spec --noconfirm
#
# L'eseguibile risultante è in  dist/  (GestionaleAssicurativo.exe su Windows).
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
    "gestionale.routes.main",
    "gestionale.routes.clients",
    "gestionale.routes.policies",
    "gestionale.routes.documents",
    "gestionale.routes.followups",
    "gestionale.routes.notifications",
    "gestionale.routes.settings",
    "flask_sqlalchemy",
    "sqlalchemy.dialects.sqlite",
    "waitress",
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

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="GestionaleAssicurativo",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # mostra l'indirizzo su cui aprire il browser
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
