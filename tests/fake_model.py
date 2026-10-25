# Copyright (C) 2026 EQQX0
# SPDX-License-Identifier: GPL-3.0-or-later
"""Builds tiny ONNX files shaped like Ultralytics YOLO exports, for testing without a trained model.

    python tests/fake_model.py out.onnx [--end2end]
"""
import sys

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper

NAMES = "{0: 'pig', 1: 'villager'}"


def build(path, end2end=False, size=64, names=NAMES):
    if end2end:     # (1, N, 6): x1, y1, x2, y2, score, class
        const = np.array([[[27, 22, 37, 42, 0.9, 0], [7, 7, 13, 13, 0.7, 1], [0, 0, 5, 5, 0.1, 0]]], np.float32)
    else:           # (1, 4 + classes, anchors): cx, cy, w, h, score per class
        boxes = np.array([[32, 32, 10, 20], [33, 32, 10, 20], [10, 10, 6, 6]], np.float32)   # 2nd overlaps 1st
        n = len(eval(names))                      # names is a dict literal like the real metadata
        scores = np.zeros((3, n), np.float32)
        scores[0, 0], scores[1, 0], scores[2, 1] = 0.9, 0.8, 0.7
        const = np.concatenate([boxes, scores], axis=1).T[None]
    nodes = [
        helper.make_node("ReduceMean", ["images"], ["m"], keepdims=1),                     # use the input...
        helper.make_node("Reshape", ["m", "shape"], ["m3"]),
        helper.make_node("Mul", ["m3", "zero"], ["z"]),                                    # ...times zero
        helper.make_node("Add", ["z", "const"], ["output0"]),
    ]
    graph = helper.make_graph(
        nodes, "fake_yolo",
        [helper.make_tensor_value_info("images", TensorProto.FLOAT, [1, 3, size, size])],
        [helper.make_tensor_value_info("output0", TensorProto.FLOAT, list(const.shape))],
        [numpy_helper.from_array(const, "const"), numpy_helper.from_array(np.zeros(1, np.float32), "zero"),
         numpy_helper.from_array(np.array([1, 1, 1], np.int64), "shape")])
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 12)])
    model.ir_version = 7
    for k, v in (("names", names), ("imgsz", "[%d, %d]" % (size, size)), ("task", "detect")):
        p = model.metadata_props.add()
        p.key, p.value = k, v
    onnx.checker.check_model(model)
    onnx.save(model, path)
    return path


if __name__ == "__main__":
    build(sys.argv[1], end2end="--end2end" in sys.argv)
    print("wrote", sys.argv[1])
