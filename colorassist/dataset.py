# Copyright (C) 2026 EQQX2
# SPDX-License-Identifier: GPL-3.0-or-later
"""Labelled screenshots on disk in YOLO format, import of downloaded datasets, and export for training.

Folder layout:
    <root>/images/<name>.jpg     screenshots
    <root>/labels/<name>.txt     one line per box: class centre_x centre_y width height (all 0..1)
                                 an empty file = "nothing to label here" (a background picture)
    <root>/classes.txt           one class name per line; the line number is the class id
"""
import ast
import os
import random
import re
import shutil
import tempfile
import time
import zipfile

import cv2
import numpy as np

IMAGE_EXT = (".jpg", ".jpeg", ".png", ".bmp", ".webp")


def default_root():
    docs = os.path.join(os.path.expanduser("~"), "Documents")
    return os.path.join(docs if os.path.isdir(docs) else os.path.expanduser("~"), "MineColorTrack dataset")


def read_image(path):
    """cv2.imread that also works with non-ASCII Windows paths."""
    data = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR) if data.size else None


def write_image(path, img):
    ext = os.path.splitext(path)[1].lower() or ".jpg"
    ok, buf = cv2.imencode(ext, img, [cv2.IMWRITE_JPEG_QUALITY, 92] if ext in (".jpg", ".jpeg") else [])
    if not ok:
        raise OSError("Could not encode image")
    buf.tofile(path)


def parse_yaml_names(text):
    """Class names from a YOLO data.yaml (inline list, inline dict, block list or block dict)."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^names\s*:\s*(.*)$", line.strip())
        if not m:
            continue
        rest = m.group(1).strip()
        if rest:
            val = ast.literal_eval(rest)
            if isinstance(val, dict):
                return [str(val[k]) for k in sorted(val, key=int)]
            return [str(v) for v in val]
        out = {}
        for nxt in lines[i + 1:]:
            if not nxt.strip() or nxt.strip().startswith("#"):
                continue
            if not nxt.startswith((" ", "\t")):
                break
            s = nxt.strip()
            if s.startswith("-"):
                out[len(out)] = s[1:].strip().strip("'\"")
            elif ":" in s:
                k, v = s.split(":", 1)
                out[int(k.strip())] = v.strip().strip("'\"")
        return [out[k] for k in sorted(out)]
    return []


class Dataset:
    def __init__(self, root):
        self.root = root
        self.img_dir = os.path.join(root, "images")
        self.lbl_dir = os.path.join(root, "labels")
        os.makedirs(self.img_dir, exist_ok=True)
        os.makedirs(self.lbl_dir, exist_ok=True)
        self.classes = []
        path = os.path.join(root, "classes.txt")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                self.classes = [ln.strip() for ln in fh if ln.strip()]

    # ---------- classes ----------
    def save_classes(self):
        with open(os.path.join(self.root, "classes.txt"), "w", encoding="utf-8") as fh:
            fh.write("\n".join(self.classes) + ("\n" if self.classes else ""))

    def add_class(self, name):
        name = name.strip()
        if not name:
            raise ValueError("A class needs a name.")
        if name.lower() in (c.lower() for c in self.classes):
            raise ValueError("There is already a class called “%s”." % name)
        self.classes.append(name)
        self.save_classes()
        return len(self.classes) - 1

    def rename_class(self, index, name):
        name = name.strip()
        if not name:
            raise ValueError("A class needs a name.")
        if any(c.lower() == name.lower() for i, c in enumerate(self.classes) if i != index):
            raise ValueError("There is already a class called “%s”." % name)
        self.classes[index] = name
        self.save_classes()

    def delete_class(self, index):
        """Remove a class and all its boxes; later class ids shift down by one."""
        for stem in self.images():
            boxes = self.load_boxes(stem)
            if boxes is None:
                continue
            new = [(c - 1 if c > index else c, *b) for (c, *b) in boxes if c != index]
            if new != boxes:
                self.save_boxes(stem, new)
        del self.classes[index]
        self.save_classes()

    # ---------- images and boxes ----------
    def images(self):
        names = [f for f in os.listdir(self.img_dir) if f.lower().endswith(IMAGE_EXT)]
        return sorted(os.path.splitext(f)[0] for f in names)

    def image_path(self, stem):
        for ext in IMAGE_EXT:
            p = os.path.join(self.img_dir, stem + ext)
            if os.path.exists(p):
                return p
        return None

    def label_path(self, stem):
        return os.path.join(self.lbl_dir, stem + ".txt")

    def load_boxes(self, stem):
        """[(class, cx, cy, w, h)] normalised, [] for a background picture, None if not labelled yet."""
        path = self.label_path(stem)
        if not os.path.exists(path):
            return None
        boxes = []
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) >= 5:
                    try:
                        c = int(float(parts[0]))
                        cx, cy, w, h = (float(v) for v in parts[1:5])
                    except ValueError:
                        continue
                    boxes.append((c, cx, cy, w, h))
        return boxes

    def save_boxes(self, stem, boxes):
        with open(self.label_path(stem), "w", encoding="utf-8") as fh:
            for c, cx, cy, w, h in boxes:
                fh.write("%d %.6f %.6f %.6f %.6f\n" % (c, cx, cy, w, h))

    def unlabel(self, stem):
        if os.path.exists(self.label_path(stem)):
            os.remove(self.label_path(stem))

    def new_stem(self, prefix="shot"):
        base = "%s_%s" % (prefix, time.strftime("%Y%m%d_%H%M%S"))
        self._seq = getattr(self, "_seq", 0)
        while True:
            self._seq += 1
            stem = "%s_%04d" % (base, self._seq)
            if not self.image_path(stem):
                return stem

    def add_image(self, frame_bgr, prefix="shot"):
        stem = self.new_stem(prefix)
        write_image(os.path.join(self.img_dir, stem + ".jpg"), frame_bgr)
        return stem

    def add_image_file(self, path):
        img = read_image(path)
        if img is None:
            raise ValueError("Not a readable image: %s" % path)
        return self.add_image(img, "img")

    def delete_image(self, stem):
        p = self.image_path(stem)
        if p:
            os.remove(p)
        self.unlabel(stem)

    # ---------- statistics and advice ----------
    def stats(self):
        per_class = [0] * len(self.classes)
        images_with = [0] * len(self.classes)
        labelled = backgrounds = 0
        stems = self.images()
        for stem in stems:
            boxes = self.load_boxes(stem)
            if boxes is None:
                continue
            labelled += 1
            if not boxes:
                backgrounds += 1
            seen = set()
            for c, *_ in boxes:
                if 0 <= c < len(per_class):
                    per_class[c] += 1
                    seen.add(c)
            for c in seen:
                images_with[c] += 1
        return {"images": len(stems), "labelled": labelled, "backgrounds": backgrounds,
                "unlabelled": len(stems) - labelled, "boxes": per_class, "images_with": images_with}

    def advice(self, st=None):
        """Short plain-language hints about what the dataset still needs."""
        st = st or self.stats()
        if not self.classes:
            return ["Add a class first, for example \u201cpig\u201d, \u201cvillager\u201d or \u201cplayer\u201d."]
        tips = []
        low = [(n, b) for n, b in zip(self.classes, st["boxes"]) if b < 50]
        for name, n in low:
            tips.append("\u201c%s\u201d: %d box%s, aim for 100 or more." % (name, n, "" if n == 1 else "es"))
        if low:
            tips.append("Vary distance, angle, light, biome and (for players) skins and armour.")
        if st["labelled"] and st["backgrounds"] < max(5, st["labelled"] // 10):
            tips.append("Add more \u201cnothing here\u201d screenshots (%d so far) so blocks are not mistaken for "
                        "targets." % st["backgrounds"])
        if st["unlabelled"]:
            tips.append("%d not labelled yet (left out of training)." % st["unlabelled"])
        return tips

    # ---------- import ----------
    def import_yolo(self, source):
        """Merge a YOLO-format dataset (zip or folder, e.g. a Roboflow “YOLOv8” export).

        Classes are matched by name; new names are added. Returns (images added, list of new class names).
        """
        tmp = None
        if os.path.isfile(source) and source.lower().endswith(".zip"):
            tmp = tempfile.mkdtemp(prefix="mct_import_")
            with zipfile.ZipFile(source) as zf:
                zf.extractall(tmp)
            folder = tmp
        else:
            folder = source
        try:
            names = []
            for dirpath, _, files in os.walk(folder):
                for f in files:
                    if f.lower() in ("data.yaml", "data.yml", "dataset.yaml"):
                        with open(os.path.join(dirpath, f), encoding="utf-8") as fh:
                            names = parse_yaml_names(fh.read())
                        break
                    if f.lower() in ("classes.txt", "obj.names"):
                        with open(os.path.join(dirpath, f), encoding="utf-8") as fh:
                            names = [ln.strip() for ln in fh if ln.strip()]
                if names:
                    break
            if not names:
                raise ValueError("No class names found (expected data.yaml or classes.txt).")
            lower = [c.lower() for c in self.classes]
            new = []
            mapping = {}
            for i, n in enumerate(names):
                if n.lower() not in lower:
                    self.classes.append(n)
                    lower.append(n.lower())
                    new.append(n)
                mapping[i] = lower.index(n.lower())
            self.save_classes()
            added = 0
            for dirpath, _, files in os.walk(folder):
                for f in files:
                    if not f.lower().endswith(IMAGE_EXT):
                        continue
                    img_path = os.path.join(dirpath, f)
                    parts = img_path.split(os.sep)
                    lbl = None
                    for k in range(len(parts) - 1, -1, -1):
                        if parts[k] == "images":
                            cand = os.sep.join(parts[:k] + ["labels"] + parts[k + 1:])
                            lbl = os.path.splitext(cand)[0] + ".txt"
                            break
                    if lbl is None or not os.path.exists(lbl):
                        continue
                    stem = self.new_stem("imp")
                    shutil.copyfile(img_path, os.path.join(self.img_dir, stem + os.path.splitext(f)[1].lower()))
                    boxes = []
                    with open(lbl, encoding="utf-8") as fh:
                        for line in fh:
                            p = line.split()
                            if len(p) == 5:
                                try:
                                    c = int(float(p[0]))
                                    vals = [float(v) for v in p[1:]]
                                except ValueError:
                                    continue
                                if c in mapping:
                                    boxes.append((mapping[c], *vals))
                    self.save_boxes(stem, boxes)
                    added += 1
            return added, new
        finally:
            if tmp:
                shutil.rmtree(tmp, ignore_errors=True)

    # ---------- export ----------
    def export_zip(self, path, val_fraction=0.15, seed=1, notebook=None):
        """Zip of labelled pictures split into train/val with data.yaml, ready for the Colab notebook."""
        if not self.classes:
            raise ValueError("There are no classes to train.")
        stems = [s for s in self.images() if self.load_boxes(s) is not None]
        if len(stems) < 2:
            raise ValueError("Label at least 2 screenshots first (more is much better).")
        rng = random.Random(seed)
        rng.shuffle(stems)
        n_val = max(1, int(round(len(stems) * val_fraction)))
        split = {"val": stems[:n_val], "train": stems[n_val:]}
        names = "\n".join("  %d: %s" % (i, n) for i, n in enumerate(self.classes))
        yaml = "# MineColorTrack dataset\ntrain: images/train\nval: images/val\nnames:\n%s\n" % names
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("data.yaml", yaml)
            zf.writestr("classes.txt", "\n".join(self.classes) + "\n")
            for part, items in split.items():
                for stem in items:
                    img = self.image_path(stem)
                    zf.write(img, "images/%s/%s%s" % (part, stem, os.path.splitext(img)[1].lower()))
                    zf.write(self.label_path(stem), "labels/%s/%s.txt" % (part, stem))
            if notebook and os.path.exists(notebook):
                zf.write(notebook, os.path.basename(notebook))
        return {"train": len(split["train"]), "val": len(split["val"]), "classes": list(self.classes)}
