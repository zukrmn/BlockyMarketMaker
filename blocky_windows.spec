# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for BlockyMarketMaker Windows distribution.
Build with: pyinstaller blocky_windows.spec --clean
"""

import os
from pathlib import Path

block_cipher = None

# Get the base directory
BASE_DIR = Path(SPECPATH)

# Data files to include
datas = [
    # Config template
    ('config.yaml', '.'),
    ('market_profiles.yaml', '.'),
    
    # Dashboard templates and static files
    ('src/dashboard/templates', 'src/dashboard/templates'),
    ('src/dashboard/static', 'src/dashboard/static'),
    
    # Images for tray icon
    ('img', 'img'),
]

# Filter out non-existent paths
datas = [(src, dst) for src, dst in datas if Path(BASE_DIR / src).exists()]

a = Analysis(
    ['tray_app.py'],
    pathex=[str(BASE_DIR), str(BASE_DIR / 'src')],
    binaries=[],
    datas=datas,
    hiddenimports=[
        # Async and web
        'asyncio',
        'aiohttp',
        'aiohttp.web',
        'aiohttp.client',
        'aiohttp.connector',
        'aiohttp.http',
        'aiohttp.http_websocket',
        'aiohttp.http_parser',
        'aiohttp_jinja2',
        'jinja2',
        'jinja2.ext',
        
        # Data handling
        'yaml',
        'json',
        'dotenv',
        
        # System Tray
        'pystray',
        'pystray._win32',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        
        # Networking
        'ssl',
        'certifi',
        'charset_normalizer',
        'multidict',
        'yarl',
        'async_timeout',
        'aiosignal',
        'frozenlist',
        
        # All src modules
        'main',
        'config',
        'blocky',
        'blocky.async_client',
        'blocky.websocket',
        'price_model',
        'spread_calculator',
        'metrics',
        'alerts',
        'health',
        'trading_helpers',
        'capital_allocator',
        'data_recorder',
        'notifications',
        'dashboard',
        'dashboard.server',
        'dashboard.candles',
        
        # Standard library
        'logging',
        'logging.handlers',
        'queue',
        'threading',
        'concurrent.futures',
        'typing',
        'webbrowser',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary modules to reduce size
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'cv2',
        'pytest',
        'unittest',
        'tkinter',  # Not needed anymore
    ],
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
    console=False,  # NO CONSOLE - clean Windows app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='img/icon.ico' if Path(BASE_DIR / 'img' / 'icon.ico').exists() else None,
)
