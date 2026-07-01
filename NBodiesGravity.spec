# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for NBodiesGravity — single-file Windows executable.
#
# Build:
#   conda run -n nbodiesgravity pyinstaller NBodiesGravity.spec
#
# Output:
#   dist/NBodiesGravity.exe   — standalone executable
#   build/                    — intermediate work files (safe to delete)

a = Analysis(
    ['nbodiesgravity/main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        # J2000 snapshot — loader.py resolves via Path(__file__).parent,
        # which in a frozen exe points into sys._MEIPASS, so the destination
        # path must mirror the source package layout exactly.
        (
            'nbodiesgravity/data/snapshots/j2000.json',
            'nbodiesgravity/data/snapshots',
        ),
    ],
    hiddenimports=[
        # PyQt6 OpenGL modules are not auto-detected by the hook
        'PyQt6.QtOpenGL',
        'PyQt6.QtOpenGLWidgets',
        # PyOpenGL dynamic dispatch — ctypes-loaded at runtime
        'OpenGL',
        'OpenGL.GL',
        'OpenGL.GL.framebufferobjects',
        'OpenGL.arrays',
        'OpenGL.arrays.numpymodule',
        'OpenGL.platform',
        'OpenGL.platform.win32',
        # HTTP stack used by JPL Horizons fetch
        'requests',
        'certifi',
        'charset_normalizer',
        'idna',
        'urllib3',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Test-only deps — keep the exe lean
        'pytest',
        'responses',
        'tkinter',
        'unittest',
        '_tkinter',
    ],
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
    name='NBodiesGravity',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    # console=False → no black terminal window for this GUI application
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
