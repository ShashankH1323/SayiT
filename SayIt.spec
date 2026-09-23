# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['D:/ZedRed/Wisper/run_app.py'],
    pathex=[],
    binaries=[],
    datas=[('D:/ZedRed/Wisper/dist', 'dist'), ('D:/ZedRed/Wisper/wisper/assets', 'wisper/assets')],
    hiddenimports=['webview', 'webview.platforms.winforms', 'clr_loader', 'pythonnet', 'sounddevice', 'soxr', 'ctranslate2', 'faster_whisper', 'keyboard', 'mouse', 'pyperclip', 'winsound', 'numpy'],
    hookspath=[],
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
    [],
    exclude_binaries=True,
    name='SayIt',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['D:/ZedRed/Wisper/say_it.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SayIt',
)
