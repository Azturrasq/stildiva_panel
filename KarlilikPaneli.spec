# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, copy_metadata

datas = []
datas += collect_data_files("streamlit", include_py_files=True)
datas += collect_data_files("streamlit_authenticator", include_py_files=True)
datas += collect_data_files("altair")
datas += collect_data_files("pydeck")
datas += collect_data_files("gspread")
datas += collect_data_files("gspread_pandas")
datas += collect_data_files("pandas")
datas += collect_data_files("webview") # YENİ EKLENDİ

datas += copy_metadata('streamlit')
datas += copy_metadata('streamlit-authenticator')

datas += [('app.py', '.'), ('config.yaml', '.'), ('secrets.json', '.'), ('logo.png', '.')]

a = Analysis(
    ['run_app.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['google.auth.transport.requests', 'webview'], # YENİ EKLENDİ
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False
)
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='KarlilikPaneli',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='logo.png'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='KarlilikPaneli'
)

app = BUNDLE(
    coll,
    name='KarlilikPaneli.app',
    icon='logo.png',
    bundle_identifier=None
)