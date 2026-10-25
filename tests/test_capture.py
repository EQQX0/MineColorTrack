# Copyright (C) 2026 EQQX0
# SPDX-License-Identifier: GPL-3.0-or-later
"""Capture back-end selection and fallback (no screen needed)."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from colorassist import capture, config  # noqa: E402


class Stub:
    def __init__(self, name, error=None):
        self.name, self.label, self.error, self.calls, self.closed = name, name, error, 0, False

    def grab(self, rect):
        self.calls += 1
        if self.error:
            raise self.error
        return np.zeros((rect[3], rect[2], 3), np.uint8)

    def close(self):
        self.closed = True


def make(fast_error=None):
    cap = capture.AutoCapture(prefer_fast=False)
    cap.compat = Stub("compatible")
    cap.fast = Stub("fast", fast_error)
    return cap


def test_fast_is_used_when_it_works():
    cap = make()
    assert cap.grab((0, 0, 8, 6)).shape == (6, 8, 3)
    assert cap.name == "fast" and cap.fast.calls == 1 and cap.compat.calls == 0


def test_falls_back_for_good_when_fast_breaks():
    cap = make(capture.CaptureError("device lost"))
    fast = cap.fast
    cap.grab((0, 0, 8, 6))
    assert cap.fast is None and fast.closed and cap.name == "compatible" and "device lost" in cap.problem
    cap.grab((0, 0, 8, 6))
    assert cap.compat.calls == 2


def test_area_across_two_screens_uses_compatible_just_once():
    cap = make(capture.CaptureError("The capture area spans more than one screen.", temporary=True))
    cap.grab((0, 0, 8, 6))
    assert cap.fast is not None and cap.compat.calls == 1


def test_setting_and_defaults():
    assert config.CaptureCfg().method == "auto"
    assert [v for v, _ in config.CHOICES[("CaptureCfg", "method")]] == ["auto", "fast", "compatible"]
    if not capture.fast_available():                     # e.g. Linux test machines
        assert capture.AutoCapture(prefer_fast=True).fast is None


def test_no_new_picture_is_temporary():
    cap = make(capture.CaptureError("Fast capture returned no new picture yet.", temporary=True))
    cap.grab((0, 0, 8, 6))
    cap.grab((0, 0, 8, 6))
    assert cap.fast is not None and cap.compat.calls == 2 and cap.problem is None
