# Copyright (C) 2026 EQQX0
# SPDX-License-Identifier: GPL-3.0-or-later
"""Choosing the ONNX Runtime execution provider, with mocked providers (no graphics card needed)."""
import logging
import os
import sys

import numpy as np
import pytest

sys.path[:0] = [os.path.join(os.path.dirname(__file__), ".."), os.path.dirname(__file__)]

from colorassist import detector  # noqa: E402

pytest.importorskip("onnxruntime")
onnx = pytest.importorskip("onnx")
import fake_model  # noqa: E402

TRT, CUDA, DML, CPU = ("TensorrtExecutionProvider", "CUDAExecutionProvider", "DmlExecutionProvider",
                       "CPUExecutionProvider")


@pytest.fixture
def providers(monkeypatch):
    """Pretend these providers are installed: providers(TRT, CUDA, CPU)."""
    def set_(*names):
        monkeypatch.setattr(detector.ort, "get_available_providers", lambda: list(names))
    monkeypatch.setattr(detector, "nvidia_driver_present", lambda: False)
    return set_


class FakeSessions:
    """Stands in for onnxruntime.InferenceSession: runs on the processor, but reports the requested provider as
    active unless told that provider fails to start (raises) or is quietly dropped by ONNX Runtime."""

    def __init__(self, monkeypatch, fail=(), drop=()):
        self.real = detector.ort.InferenceSession
        self.fail, self.drop, self.calls = set(fail), set(drop), []
        monkeypatch.setattr(detector.ort, "InferenceSession", self)

    def __call__(self, path, sess_options=None, providers=None):
        first = providers[0][0] if isinstance(providers[0], tuple) else providers[0]
        self.calls.append(providers)
        if first in self.drop:
            print("*** EP Error *** Falling back to ['CPUExecutionProvider'] and retrying.")   # as ONNX Runtime does
        if first in self.fail:
            raise RuntimeError("LoadLibrary failed with error 126 for %s" % first)
        sess = self.real(path, sess_options=sess_options, providers=[CPU])
        active = [CPU] if first in self.drop else [first, CPU]
        return _Reporting(sess, active)


class _Reporting:
    def __init__(self, sess, active):
        self._sess, self._active = sess, active

    def get_providers(self):
        return self._active

    def __getattr__(self, name):
        return getattr(self._sess, name)


def test_plan_order_and_device_setting(providers):
    providers(TRT, CUDA, CPU)
    assert [k for k, _ in detector.plan("auto")[0]] == ["tensorrt", "cuda", "cpu"]
    assert [k for k, _ in detector.plan("cuda")[0]] == ["cuda", "cpu"]
    assert [k for k, _ in detector.plan("cpu")[0]] == ["cpu"]
    providers(DML, CPU)
    assert [k for k, _ in detector.plan("auto")[0]] == ["directml", "cpu"]
    chain, notes = detector.plan("tensorrt")                    # NVIDIA chosen, DirectML build installed
    assert [k for k, _ in chain] == ["directml", "cpu"] and "onnxruntime-gpu" in notes[0]
    providers(TRT, CUDA, DML, CPU)
    assert [k for k, _ in detector.plan("auto")[0]] == ["tensorrt", "cuda", "directml", "cpu"]
    assert [k for k, _ in detector.plan("directml")[0]] == ["directml", "cpu"]
    assert [k for k, _ in detector.plan("nonsense")[0]][0] == "tensorrt"
    providers()                                                  # odd build listing nothing: processor anyway
    assert detector.plan("auto")[0] == [("cpu", CPU)]


def test_nvidia_card_hint_on_directml_build(providers, monkeypatch):
    providers(DML, CPU)
    monkeypatch.setattr(detector, "nvidia_driver_present", lambda: True)
    assert "NVIDIA graphics card found" in detector.plan("auto")[1][0]


def test_tensorrt_used_with_fp16_and_engine_cache(tmp_path, providers, monkeypatch):
    providers(TRT, CUDA, CPU)
    fake = FakeSessions(monkeypatch)
    model = fake_model.build(str(tmp_path / "m.onnx"))
    cache = str(tmp_path / "trt_cache")
    assert detector.needs_trt_build(model, "auto", True, cache)
    det = detector.Detector(model, device="auto", fp16=True, cache_dir=cache)
    assert det.provider == "tensorrt" and det.device == "GPU" and det.device_label == "TensorRT FP16 (NVIDIA)"
    assert det.notice is None and not det.fallbacks
    trt_call = fake.calls[-1]
    name, opts = trt_call[0]
    assert name == TRT and trt_call[1:] == [CUDA, CPU]           # CUDA, then CPU, run layers TensorRT cannot
    assert opts["trt_fp16_enable"] is True and opts["trt_engine_cache_enable"] is True
    assert opts["trt_engine_cache_path"] == detector.trt_cache_folder(model, cache, True)
    assert os.path.dirname(opts["trt_engine_cache_path"]) == cache and opts["trt_timing_cache_path"] == cache
    assert detector.trt_cache_folder(model, cache, False) != opts["trt_engine_cache_path"]   # FP32 kept apart
    open(os.path.join(opts["trt_engine_cache_path"], "x_sm89.engine"), "wb").close()
    assert not detector.needs_trt_build(model, "auto", True, cache)
    assert detector.needs_trt_build(model, "auto", False, cache)
    assert not detector.needs_trt_build(model, "cuda", True, cache)


def test_onnxruntime_fallback_text_stays_off_stdout(tmp_path, providers, monkeypatch, capsys, caplog):
    providers(CUDA, CPU)
    FakeSessions(monkeypatch, drop={CUDA})
    with caplog.at_level(logging.INFO, logger="minecolortrack.ai"):
        det = detector.Detector(fake_model.build(str(tmp_path / "m.onnx")))
    assert det.provider == "cpu" and capsys.readouterr().out == ""     # `mct` prints only JSON there
    assert any("EP Error" in r.getMessage() for r in caplog.records)


def test_falls_back_and_logs_when_nvidia_libraries_missing(tmp_path, providers, monkeypatch, caplog):
    providers(TRT, CUDA, CPU)
    FakeSessions(monkeypatch, fail={TRT}, drop={CUDA})          # TensorRT raises; CUDA quietly not started
    monkeypatch.setattr(detector, "_loadable", lambda name: "cudnn" not in name)
    model = fake_model.build(str(tmp_path / "m.onnx"))
    with caplog.at_level(logging.WARNING, logger="minecolortrack.ai"):
        det = detector.Detector(model, device="auto", cache_dir=str(tmp_path / "c"))
    assert det.provider == "cpu" and det.device == "CPU"
    assert [k for k, _ in det.fallbacks] == ["tensorrt", "cuda"]
    assert "cuDNN 9" in det.fallbacks[0][1] and "TensorRT 10" in det.fallbacks[0][1]
    assert det.notice.startswith("TensorRT and CUDA could not start") and det.notice.count("cuDNN 9") == 2
    assert det.notice.endswith("Using processor (CPU).")      # once in "missing", once in the requirements
    logged = " ".join(r.getMessage() for r in caplog.records)
    assert TRT in logged and CUDA in logged
    found = det.detect(np.zeros((128, 128, 3), np.uint8), conf=0.5)   # still detects, on the processor
    assert sorted(d.cls for d in found) == [0, 1]


def test_falls_back_to_directml_after_nvidia(tmp_path, providers, monkeypatch):
    providers(TRT, CUDA, DML, CPU)
    FakeSessions(monkeypatch, fail={TRT, CUDA})
    det = detector.Detector(fake_model.build(str(tmp_path / "m.onnx")), device="tensorrt")
    assert det.provider == "directml" and det.device_label == "DirectML (graphics card)"
    assert "Using DirectML" in det.notice


def test_warmup_failure_counts_as_provider_failure(tmp_path, providers, monkeypatch):
    providers(CUDA, CPU)
    fake = FakeSessions(monkeypatch)
    model = fake_model.build(str(tmp_path / "m.onnx"))
    real_call = fake.__call__

    def broken_run(path, sess_options=None, providers=None):
        sess = real_call(path, sess_options, providers)
        if sess.get_providers()[0] == CUDA:
            def run(*a, **k):
                raise RuntimeError("CUDA out of memory")
            sess.run = run
        return sess
    monkeypatch.setattr(detector.ort, "InferenceSession", broken_run)
    det = detector.Detector(model, device="auto")
    assert det.provider == "cpu" and "out of memory" in det.fallbacks[0][1]


def test_bad_model_fails_once_without_provider_noise(tmp_path, providers, monkeypatch):
    providers(TRT, CUDA, CPU)
    bad = tmp_path / "bad.onnx"
    bad.write_bytes(b"not a model")
    fake = FakeSessions(monkeypatch)
    with pytest.raises(detector.ModelError):
        detector.Detector(str(bad))
    assert len(fake.calls) == 1 and fake.calls[0] == [CPU]


def test_requirements_follow_the_cuda_build(monkeypatch):
    monkeypatch.setattr(detector, "cuda_build_version", lambda: "13.0")
    text = detector.requirements_text("tensorrt")
    assert "CUDA 13.0" in text and "580" in text and "TensorRT 10 for CUDA 13" in text
    monkeypatch.setattr(detector, "cuda_build_version", lambda: "12.8")
    text = detector.requirements_text("cuda")
    assert "CUDA 12.8" in text and "570.65" in text and "TensorRT" not in text
    missing = detector.missing_libraries("tensorrt", loader=lambda name: False)
    assert len(missing) == 5 and any("TensorRT 10" in m for m in missing)


def test_compare_detections():
    D = detector.Detection
    ref = [D(0, 10, 10, 20, 40, 0.9), D(1, 100, 50, 30, 30, 0.8)]
    near = [D(1, 100.5, 50, 30, 30.5, 0.79), D(0, 10, 11, 20, 39, 0.91)]
    c = detector.compare_detections(ref, near)
    assert (c["matched"], c["missing"], c["extra"]) == (2, 0, 0) and c["max_shift_px"] == 1.0
    assert abs(c["max_confidence_change"] - 0.01) < 1e-6
    c = detector.compare_detections(ref, [D(0, 10, 10, 20, 40, 0.9), D(0, 300, 300, 5, 5, 0.5)])
    assert (c["matched"], c["missing"], c["extra"]) == (1, 1, 1)


def test_engine_loads_model_in_background_and_shows_building(tmp_path, monkeypatch):
    import threading
    from colorassist import config, engine
    cfg = config.default_config()
    det_cfg = cfg.profile.detection
    det_cfg.enabled, det_cfg.model_path = True, fake_model.build(str(tmp_path / "m.onnx"))
    cfg.profile.targets = [config.Target(name="green", color="#00FF00", min_area=10)]
    release, real = threading.Event(), detector.Detector

    def slow_detector(path, device, fp16, cache_dir):
        release.wait(10)                                    # a TensorRT engine build that takes a while
        return real(path, "cpu", fp16, cache_dir)
    monkeypatch.setattr(detector, "Detector", slow_detector)
    monkeypatch.setattr(detector, "needs_trt_build", lambda *a: True)
    eng = engine.Engine(cfg, str(tmp_path / "trt_cache"))
    eng._thread = threading.current_thread()                # behave as inside the live capture loop
    frame = np.zeros((128, 128, 3), np.uint8)
    frame[10:40, 10:40] = (0, 255, 0)
    res = eng.process(frame, (0, 0, 128, 128), capture_ms=2.0)
    assert res.ai_status == engine.BUILDING and res.ai_error is None
    assert [t[5] for t in res.tracks] == ["green"]          # colour targets keep working meanwhile
    assert set(res.timings) == {"capture", "colour", "postprocess", "draw"}
    release.set()
    for _ in range(200):
        if eng._loading_key is None:
            break
        __import__("time").sleep(0.02)
    res = eng.process(frame, (0, 0, 128, 128), capture_ms=2.0)
    assert res.ai_status is None and res.ai_error is None and res.ai_label == "processor (CPU)", res.ai_error
    assert sorted(t[5] for t in res.tracks) == ["green", "pig", "villager"]
    assert set(res.timings) == set(engine.STAGES) and all(v >= 0 for v in res.timings.values())


def test_changed_settings_replace_a_load_in_progress(tmp_path, monkeypatch):
    import threading
    from colorassist import config, engine
    cfg = config.default_config()
    cfg.profile.detection.enabled = True
    cfg.profile.detection.model_path = fake_model.build(str(tmp_path / "m.onnx"))
    monkeypatch.setattr(detector, "needs_trt_build", lambda *a: False)
    eng = engine.Engine(cfg, str(tmp_path / "c"))
    eng._loading_key = ("old", "auto", True, "c")            # an older load still running ...
    eng._load(("old", "auto", True, "c"))                   # ... finishes: it may not be used for the new key
    eng._loading_key = ("new", "cpu", True, "c")
    eng._load(("old", "auto", True, "c"))
    assert eng._detector_key == ("old", "auto", True, "c") and eng._loading_key == ("new", "cpu", True, "c")
    eng._thread = threading.current_thread()
    res = eng.process(np.zeros((64, 64, 3), np.uint8), (0, 0, 64, 64))
    assert res.ai_status == "Loading the AI model"


def test_warnings_go_to_error_log(tmp_path):
    import logging
    from colorassist import app
    old_hook, logger = sys.excepthook, logging.getLogger("minecolortrack")
    before = list(logger.handlers)
    try:
        app._install_error_log(str(tmp_path / "config.json"))
        logging.getLogger("minecolortrack.ai").warning("AI provider TensorrtExecutionProvider failed: test")
        for h in logger.handlers:
            h.flush()
        text = (tmp_path / "error.log").read_text(encoding="utf-8")
        assert "WARNING minecolortrack.ai: AI provider TensorrtExecutionProvider failed: test" in text
    finally:
        for h in logger.handlers[len(before):]:
            logger.removeHandler(h)
            h.close()
        sys.excepthook = old_hook


def test_benchmark_compares_devices_with_cpu(tmp_path, providers, monkeypatch):
    providers(TRT, CUDA, CPU)
    FakeSessions(monkeypatch, fail={CUDA})
    model = fake_model.build(str(tmp_path / "m.onnx"))
    res = detector.benchmark(model, np.zeros((128, 128, 3), np.uint8), runs=3, cache_dir=str(tmp_path / "c"),
                             conf=0.5)
    by = {(r["device"], r["fp16"]): r for r in res}
    assert list(by) == [("cpu", False), ("tensorrt", True), ("tensorrt", False), ("cuda", False)]
    assert by[("cpu", False)]["detections"] == 2 and set(by[("cpu", False)]["ms"]) == {
        "preprocess", "inference", "postprocess", "total"}
    same = by[("tensorrt", True)]["vs_cpu_fp32"]            # fake TensorRT runs the CPU model: identical boxes
    assert same["matched"] == 2 and same["missing"] == same["extra"] == 0 and same["max_shift_px"] == 0
    assert "skipped" in by[("cuda", False)] and "CUDA could not start" in by[("cuda", False)]["skipped"]
