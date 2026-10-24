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

common = dict(
    pathex=[root],
    hiddenimports=hidden + ["colorassist.cli"],
    datas=[(os.path.join(root, "colorassist", "assets"), os.path.join("colorassist", "assets"))],
    excludes=["tkinter", "PIL", "pytest", "matplotlib", "IPython", "onnx", "torch", "torchvision", "ultralytics",
              "scipy", "pandas", "polars", "sympy"],
    noarchive=False,
)
# Two programs sharing one folder: the windowed app and the `mct` command-line tool (needs a console).
a = Analysis([os.path.join(root, "run.py")], **common)
b = Analysis([os.path.join(root, "mct.py")], **common)
app_exe = EXE(PYZ(a.pure), a.scripts, [], exclude_binaries=True, name="MineColorTrack", console=False,
              icon=icon, upx=False)
cli_exe = EXE(PYZ(b.pure), b.scripts, [], exclude_binaries=True, name="mct", console=True, icon=icon, upx=False)
coll = COLLECT(app_exe, a.binaries, a.datas, cli_exe, b.binaries, b.datas, name="MineColorTrack", upx=False)
