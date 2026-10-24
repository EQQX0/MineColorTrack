# PyInstaller build recipe. Run from the repository root:  pyinstaller --noconfirm packaging/MineColorTrack.spec
import os

root = os.path.abspath(os.path.join(SPECPATH, ".."))
icon = os.path.join(root, "colorassist", "assets", "icon.ico")

from PyInstaller.utils.hooks import collect_submodules

hidden = []
for pkg in ("dxcam", "comtypes"):          # Windows fast capture; imported lazily, so list it explicitly
    try:
        hidden += collect_submodules(pkg)
    except Exception:
        pass

a = Analysis(
    [os.path.join(root, "run.py")],
    pathex=[root],
    hiddenimports=hidden,
    datas=[(os.path.join(root, "colorassist", "assets"), os.path.join("colorassist", "assets"))],
    excludes=["tkinter", "PIL", "pytest", "matplotlib", "IPython", "onnx", "torch", "torchvision", "ultralytics",
              "scipy", "pandas", "polars", "sympy"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MineColorTrack",
    console=False,
    icon=icon,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="MineColorTrack", upx=False)
