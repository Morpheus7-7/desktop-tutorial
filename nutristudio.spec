# PyInstaller spec — NutriStudio (eseguibile «one-file»)
#
# Costruzione:
#     pip install -r requirements-build.txt
#     pyinstaller nutristudio.spec --noconfirm
#
# L'eseguibile risultante è in  dist/  (NutriStudio.exe su Windows).
# Per l'altra applicazione di questo repository vedi gestionale.spec.

block_cipher = None

# Template, file statici e banca dati degli alimenti: senza il JSON in datas
# l'eseguibile partirebbe con il database alimenti vuoto.
datas = [
    ("nutriapp/templates", "nutriapp/templates"),
    ("nutriapp/static", "nutriapp/static"),
    ("nutriapp/data", "nutriapp/data"),
]

# I blueprint sono importati dentro register_blueprints(): PyInstaller non li
# vede da solo e vanno dichiarati.
hiddenimports = [
    "nutriapp.routes.auth",
    "nutriapp.routes.main",
    "nutriapp.routes.clients",
    "nutriapp.routes.plans",
    "nutriapp.routes.shopping",
    "nutriapp.routes.foods",
    "nutriapp.routes.recipes",
    "nutriapp.routes.blog",
    "nutriapp.routes.portal",
    "nutriapp.routes.settings",
    "flask_sqlalchemy",
    "sqlalchemy.dialects.sqlite",
    "waitress",
]

a = Analysis(
    ["run_nutristudio.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Le email usano solo ssl/smtplib della stdlib: cryptography non serve.
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
    name="NutriStudio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # mostra l'indirizzo e le credenziali del primo accesso
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
