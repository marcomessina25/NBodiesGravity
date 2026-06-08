# Building NBodiesGravity.exe

Step-by-step guide for producing a standalone Windows executable from source.

---

## Prerequisites

| Requirement | Version used | Notes |
|---|---|---|
| Miniconda / Anaconda | any | Must have the `nbodiesgravity` conda env |
| Python | 3.12 | Managed by conda |
| PyInstaller | 6.20.0 | Already in `nbodiesgravity` env |
| PyQt6 | 6.11.0 | Already in `nbodiesgravity` env |
| PyOpenGL | 3.1.x | Already in `nbodiesgravity` env |
| NumPy | 2.x | Already in `nbodiesgravity` env |
| UPX (optional) | any | Reduces exe size if present in PATH |

> **Note:** All Python dependencies are satisfied by the existing `environment.yml`. No additional installs are needed before building.

---

## Quick build

Run this single command from the project root (`C:\Projects\NBodiesGravity\`):

```bash
conda run -n nbodiesgravity pyinstaller NBodiesGravity.spec --noconfirm
```

Output:

| Path | Contents |
|---|---|
| `dist/NBodiesGravity.exe` | Standalone single-file executable (~53 MB) |
| `build/NBodiesGravity/` | Intermediate work files — safe to delete |

---

## What the spec does

The spec file is `NBodiesGravity.spec` in the project root. Key settings:

### Entry point
```
nbodiesgravity/main.py
```

### Bundled data files

The J2000 solar system snapshot is the only non-Python resource the app requires to start without a network connection. It is embedded into the exe and extracted to the correct location at runtime.

| Source | Destination inside exe |
|---|---|
| `nbodiesgravity/data/snapshots/j2000.json` | `nbodiesgravity/data/snapshots/j2000.json` |

The destination path mirrors the source package layout exactly. This is required because `loader.py` resolves the file via `Path(__file__).parent / "snapshots" / "j2000.json"` — in a frozen exe, `__file__` points into `sys._MEIPASS`, so the relative layout must be preserved.

### Hidden imports

PyInstaller's static analysis cannot detect all runtime imports. The spec explicitly declares:

```
PyQt6.QtOpenGL, PyQt6.QtOpenGLWidgets   — OpenGL widget support
OpenGL, OpenGL.GL, OpenGL.arrays, ...   — PyOpenGL ctypes dispatch
OpenGL.platform.win32                   — Windows OpenGL platform backend
requests, certifi, charset_normalizer,
idna, urllib3                           — HTTP stack for JPL Horizons
```

### Excluded modules

Test-only dependencies (`pytest`, `responses`) and the unused `tkinter` stdlib module are excluded to keep the exe size down.

### Mode

`console=False` — the application is a pure GUI; no terminal window is shown.

---

## Runtime data written at runtime (not bundled)

The JPL Horizons cache is written to the user's home directory at runtime and does **not** need to be bundled:

```
~/.nbodiesgravity/cache.json
```

This directory is created automatically on first use.

---

## Rebuilding after code changes

Re-run the same command. PyInstaller detects changed `.toc` files and rebuilds only what is necessary:

```bash
conda run -n nbodiesgravity pyinstaller NBodiesGravity.spec --noconfirm
```

To force a completely clean build, delete the work directory first:

```bash
rm -rf build/NBodiesGravity
conda run -n nbodiesgravity pyinstaller NBodiesGravity.spec --noconfirm
```

---

## Adding new data files

If new static resources are added to the package (e.g. icons, additional snapshots), add an entry to the `datas` list in `NBodiesGravity.spec`:

```python
datas=[
    ('nbodiesgravity/data/snapshots/j2000.json', 'nbodiesgravity/data/snapshots'),
    # Add new entries here:
    # ('nbodiesgravity/path/to/resource.ext', 'nbodiesgravity/path/to'),
],
```

The second element of each tuple is the **destination folder** inside the exe's extraction directory — it must match the directory that the source code expects when resolving paths via `Path(__file__).parent`.

---

## Updating the conda environment

If new Python dependencies are added to `environment.yml`, update the environment before building:

```bash
conda env update -n nbodiesgravity -f environment.yml --prune
```

Then rebuild the exe.

---

## Troubleshooting

### App starts but immediately closes (no error)
Run the build temporarily with `console=True` in `NBodiesGravity.spec` to see the Python traceback in a terminal window:
```python
console=True,
```

### `j2000.json` not found at startup
The JSON data file was not bundled. Verify the `datas` entry in `NBodiesGravity.spec` matches the path in `nbodiesgravity/data/snapshots/j2000.json` and rebuild.

### OpenGL error / black screen
The GPU driver must support OpenGL 3.3 Core Profile. This is a system requirement and cannot be resolved in the build.

### `MSVCR90.dll` warnings during build
These warnings come from legacy VC9 DLLs inside PyOpenGL's `DLLS/` folder (unused freeglut builds). They are harmless and do not affect the executable.

### Antivirus flags the exe
Single-file PyInstaller executables self-extract to `%TEMP%` at launch. This behaviour is sometimes flagged by antivirus software. Switching to a one-directory build (`onedir=True` instead of the `EXE` all-in-one mode) avoids this.
