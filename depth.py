"""Depth maps for the 3D camera effect (Depth Anything V2 Small, runs on CPU). Falls back to a generic depth shape if the model is unavailable."""
from pathlib import Path
import numpy as np
import cv2
from PIL import Image

_pipe, _failed = None, False


def synthetic(w, h):
    """generic 'subject in the middle is near' depth, used only when the model cannot run"""
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.exp(-(((x / w - 0.5) / 0.32) ** 2 + ((y / h - 0.55) / 0.5) ** 2))
    return (0.15 + 0.85 * d).astype(np.float32)


def _model(cfg):
    global _pipe, _failed
    if _pipe is None and not _failed:
        try:
            from transformers import pipeline
            _pipe = pipeline("depth-estimation", model=cfg.get("depth_model", "depth-anything/Depth-Anything-V2-Small-hf"), device=-1)
            print("  depth model loaded")
        except Exception as e:
            _failed = True
            print("  depth model unavailable, using a generic depth shape instead:", str(e)[:150])
    return _pipe


def depth_for(image_path, cfg):
    """float32 array 0..1 (1 = near) at the image's resolution; cached next to the image"""
    cache = Path(str(image_path) + ".depth.png")
    img = Image.open(image_path).convert("RGB")
    w, h = img.size
    if cache.exists():
        return np.asarray(Image.open(cache), dtype=np.float32) / 255.0
    d = None
    pipe = _model(cfg)
    if pipe is not None:
        try:
            out = pipe(img)["depth"]
            d = np.asarray(out.resize((w, h)), dtype=np.float32)
            lo, hi = np.percentile(d, 2), np.percentile(d, 98)
            d = np.clip((d - lo) / max(hi - lo, 1e-6), 0, 1)
            d = cv2.GaussianBlur(d, (0, 0), 3)  # smooth edges so the parallax does not tear
        except Exception as e:
            print("  depth failed for one picture:", str(e)[:120])
    if d is None:
        d = synthetic(w, h)
    Image.fromarray((d * 255).astype(np.uint8)).save(cache)
    return d.astype(np.float32)
