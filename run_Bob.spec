# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import copy_metadata

import os
import pathlib
import glob



streamlit_root = "venv/lib/python3.13/site-packages/streamlit"

all_data = collect_data_files("streamlit")

all_data += copy_metadata('docling')

all_data += copy_metadata('docling-ibm-models')

all_data += copy_metadata('docling-parse')

all_data += collect_data_files("docling")


# add the prof images for user and assistant (include everything in the assets folder)
for f in glob.glob("Assets/*"):
    all_data.append((f, "Assets"))

all_data += [
    (os.path.join(streamlit_root, "web"), "streamlit/web"),
    ("venv/lib/python3.13/site-packages/altair/vegalite/v5/schema/vega-lite-schema.json", "./altair/vegalite/v5/schema/"),
    ("venv/lib/python3.13/site-packages/streamlit/static", "./streamlit/static"),
    ("venv/lib/python3.13/site-packages/streamlit/runtime", "./streamlit/runtime"),
    ("Bob.py", "."),
    ("Styling/bobStyle.css", "Styling"),
    (".streamlit/config.toml", ".streamlit"),
]


a = Analysis(
    ['run_Bob.py'],
    pathex=[],
    binaries=[],
    datas=all_data,
    hiddenimports=["ollama", "config", "uuid", "pypdf", "pandas", "docx", "docling", "docling.document_converter", "docling.models.plugins"],
    hookspath=['./hooks'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='BobAI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
