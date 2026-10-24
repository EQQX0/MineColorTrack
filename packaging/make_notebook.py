"""Writes colorassist/assets/train_minecolortrack.ipynb (the Google Colab training notebook).

Lines ending in "# colab-only" are skipped by tests/test_training_e2e.py, which runs the rest locally.
"""
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "colorassist", "assets", "train_minecolortrack.ipynb")


def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").splitlines(True)}


def code(text):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
            "source": text.strip("\n").splitlines(True)}


CELLS = [
    md("""
# Train a MineColorTrack entity model

This notebook turns the screenshots you labelled in MineColorTrack into an AI model that finds those
entities (for example pig, villager or player) on your screen.

1. **Runtime > Change runtime type > T4 GPU** (free), then **Save**.
2. Run the cells from top to bottom (the play button on each cell, or **Runtime > Run all**).
3. When asked, upload the zip you made with **Export for training** in MineColorTrack.
4. At the end the browser downloads **minecolortrack_model.onnx**. In MineColorTrack open
   **Entities > Load model** and choose that file.

Training uses [Ultralytics YOLO](https://docs.ultralytics.com) (AGPL-3.0 licence).
"""),
    md("## 1. Install the training library"),
    code("""
!pip install -q ultralytics  # colab-only
"""),
    md("## 2. Settings\nThe defaults are a good start. Bigger models (s, m) are more accurate but slower in MineColorTrack."),
    code("""
MODEL = "yolo26n.pt"      # n = fastest (recommended), s = more accurate, m = slowest
EPOCHS = 100              # passes over your pictures; training stops early when it stops improving
IMAGE_SIZE = 640          # must stay 640 unless you know why
DATA_DIR = "/content/mct_dataset"
"""),
    md("## 3. Upload your exported zip"),
    code("""
from google.colab import files  # colab-only
uploaded = files.upload()  # colab-only
ZIP_PATH = next(iter(uploaded))  # colab-only
print("Uploaded:", ZIP_PATH)
"""),
    md("## 4. Train\nThis takes about 10 to 30 minutes on the free GPU, depending on how many pictures you have."),
    code("""
import os, shutil, zipfile
from ultralytics import YOLO

def prepare(zip_path, data_dir):
    shutil.rmtree(data_dir, ignore_errors=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(data_dir)
    yaml_path = os.path.join(data_dir, "data.yaml")
    with open(yaml_path, encoding="utf-8") as fh:
        text = fh.read()
    with open(yaml_path, "w", encoding="utf-8") as fh:
        fh.write("path: %s\\n" % data_dir + text)
    return yaml_path

yaml_path = prepare(ZIP_PATH, DATA_DIR)
model = YOLO(MODEL)
model.train(data=yaml_path, epochs=EPOCHS, imgsz=IMAGE_SIZE, patience=30,
            project="/content/runs", name="minecolortrack", exist_ok=True)
SAVE_DIR = str(model.trainer.save_dir)
print("Training finished. Results in", SAVE_DIR)
"""),
    md("## 5. Check how good it is\nmAP50 near 1.0 is excellent; below about 0.5, label more pictures (and more background pictures)."),
    code("""
best = os.path.join(SAVE_DIR, "weights", "best.pt")
metrics = YOLO(best).val(data=yaml_path, imgsz=IMAGE_SIZE)
print("mAP50: %.2f   mAP50-95: %.2f" % (metrics.box.map50, metrics.box.map))
for i, name in YOLO(best).names.items():
    print("  %-20s mAP50 %.2f" % (name, metrics.box.ap50[i] if i < len(metrics.box.ap50) else float("nan")))
"""),
    md("## 6. Export for MineColorTrack and download"),
    code("""
onnx_path = YOLO(best).export(format="onnx", imgsz=IMAGE_SIZE, opset=12, simplify=True)
FINAL = os.path.join(os.path.dirname(DATA_DIR), "minecolortrack_model.onnx")
shutil.copyfile(onnx_path, FINAL)
print("Model ready:", FINAL)
files.download(FINAL)  # colab-only
"""),
]

nb = {"cells": CELLS, "metadata": {"accelerator": "GPU", "colab": {"provenance": []},
                                   "kernelspec": {"display_name": "Python 3", "name": "python3"},
                                   "language_info": {"name": "python"}},
      "nbformat": 4, "nbformat_minor": 0}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(nb, fh, indent=1)
print("notebook written to", OUT)
