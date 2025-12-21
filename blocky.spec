# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for BlockyMarketMaker
Build with: pyinstaller blocky.spec
"""

import os
from pathlib import Path

block_cipher = None

# Get the base directory
BASE_DIR = Path(SPECPATH)

# Collect all source files
src_files = []
for root, dirs, files in os.walk(BASE_DIR / 'src'):
    for file in files:
        if file.endswith('.py'):
            src_path = Path(root) / file
            dest_path = Path(root).relative_to(BASE_DIR)
            src_files.append((str(src_path), str(dest_path)))

# Data files to include
datas = [
    # Config template
    ('config.yaml', '.'),
    
    # Dashboard templates and static files
    ('src/dashboard/templates', 'src/dashboard/templates'),
    ('src/dashboard/static', 'src/dashboard/static'),
    
    # Images
    ('img', 'img'),
    
    # Scripts
    ('scripts/gui_setup.py', 'scripts'),
    
    # Run script
    ('run.py', '.'),
]

# Filter out non-existent paths
datas = [(src, dst) for src, dst in datas if Path(BASE_DIR / src).exists()]

a = Analysis(
    ['launcher.py'],
    pathex=[str(BASE_DIR), str(BASE_DIR / 'src')],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'aiohttp',
        'aiohttp_jinja2',
        'jinja2',
        'yaml',
        'dotenv',
        'asyncio',
        'tkinter',
        'tkinter.ttk',
        'tkinter.messagebox',
        'tkinter.scrolledtext',
        # All src modules
        'blocky',
        'blocky.async_client',
        'blocky.websocket',
        'price_model',
        'spread_calculator',
        'metrics',
        'alerts',
        'config',
        'health',
        'trading_helpers',
        'data_recorder',
        'dashboard',
        'dashboard.server',
        'dashboard.candles',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='BlockyMarketMaker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Show console for logs
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='img/icon.ico',  # Uncomment if you have an icon
)
