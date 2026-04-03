# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for TTS2MP3 Studio macOS .app bundle.

Uses pywebview + embedded FastAPI server to render the web UI
in a native macOS WebKit window.
"""

import os
import sys

block_cipher = None
project_root = os.path.dirname(os.path.abspath(SPECPATH))

a = Analysis(
    [os.path.join(project_root, 'desktop.py')],
    pathex=[project_root],
    binaries=[],
    datas=[
        # Web UI assets
        (os.path.join(project_root, 'web'), 'web'),
        # Server package
        (os.path.join(project_root, 'server'), 'server'),
        # Engine package
        (os.path.join(project_root, 'engine'), 'engine'),
    ],
    hiddenimports=[
        # Server
        'uvicorn',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'fastapi',
        'fastapi.middleware',
        'fastapi.middleware.cors',
        'fastapi.staticfiles',
        'fastapi.responses',
        'starlette',
        'starlette.responses',
        'starlette.staticfiles',
        'starlette.middleware',
        'python_multipart',
        'anyio',
        'anyio._backends',
        'anyio._backends._asyncio',
        # Engine
        'edge_tts',
        'edge_tts.communicate',
        'edge_tts.voices',
        'edge_tts.drm',
        'edge_tts.constants',
        'edge_tts.exceptions',
        'edge_tts.submaker',
        'edge_tts.data_classes',
        'edge_tts.typing',
        'edge_tts.util',
        'striprtf',
        'striprtf.striprtf',
        'ebooklib',
        'ebooklib.epub',
        'ebooklib.utils',
        'bs4',
        'bs4.builder',
        'bs4.builder._lxml',
        'bs4.builder._html5lib',
        'bs4.builder._htmlparser',
        'xml.etree.ElementTree',
        'html.parser',
        'certifi',
        'aiohttp',
        'aiohttp.web',
        'lxml',
        'lxml.etree',
        'six',
        # pywebview
        'webview',
        'webview.platforms',
        'webview.platforms.cocoa',
        'objc',
        'Foundation',
        'AppKit',
        'WebKit',
        'bottle',
        'proxy_tools',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'fitz',
        'pymupdf',
        'PyMuPDF',
        'matplotlib',
        'numpy',
        'scipy',
        'pandas',
        'PIL',
        'cv2',
        'tkinter',
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
    [],
    exclude_binaries=True,
    name='TTS2MP3 Studio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(project_root, 'build', 'TTS2MP3.icns'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='TTS2MP3 Studio',
)

app = BUNDLE(
    coll,
    name='TTS2MP3 Studio.app',
    icon=os.path.join(project_root, 'build', 'TTS2MP3.icns'),
    bundle_identifier='com.tts2mp3.studio',
    info_plist={
        'CFBundleName': 'TTS2MP3 Studio',
        'CFBundleDisplayName': 'TTS2MP3 Studio',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleVersion': '1.0.0',
        'CFBundleIdentifier': 'com.tts2mp3.studio',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '10.15.0',
        'NSAppTransportSecurity': {
            'NSAllowsLocalNetworking': True,
        },
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'TTS2MP3 Project',
                'CFBundleTypeExtensions': ['tts2mp3'],
                'CFBundleTypeRole': 'Editor',
            },
        ],
    },
)
