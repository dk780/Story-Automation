"""Fonts: Kalam (free handwriting font, OFL) is downloaded once at run time; Poppins is the bundled fallback.
Colour emoji (Noto, OFL) are the icons."""
import io, zipfile
from pathlib import Path
import requests
from PIL import ImageFont

ASSETS = Path(__file__).parent / "assets" / "fonts"
EMOJI, MONO, SANS = ASSETS / "NotoColorEmoji.ttf", ASSETS / "DejaVuSansMono-Bold.ttf", ASSETS / "Poppins-Bold.ttf"
HAND_TTF_URLS = ["https://github.com/google/fonts/raw/main/ofl/kalam/Kalam-Bold.ttf",
                 "https://raw.githubusercontent.com/google/fonts/main/ofl/kalam/Kalam-Bold.ttf"]
HAND_ZIP_URL = "https://github.com/itfoundry/kalam/releases/download/v2.001/Kalam-2_001.zip"
_cache, _hand = {}, None


def _valid(path):
    try:
        ImageFont.truetype(str(path), 40)
        return True
    except Exception:
        return False


def hand_path():
    global _hand
    if _hand:
        return _hand
    for name in ("Kalam-Bold.ttf", "Kalam-Bold.otf"):
        p = ASSETS / name
        if p.exists() and _valid(p):
            _hand = p; return p
    for url in HAND_TTF_URLS:
        try:
            r = requests.get(url, timeout=60)
            if r.status_code == 200 and len(r.content) > 50_000:
                p = ASSETS / "Kalam-Bold.ttf"; p.write_bytes(r.content)
                if _valid(p):
                    print("  handwriting font ready (Kalam)"); _hand = p; return p
        except Exception:
            pass
    try:
        r = requests.get(HAND_ZIP_URL, timeout=90)
        z = zipfile.ZipFile(io.BytesIO(r.content))
        for n in z.namelist():
            if n.endswith("Kalam-Bold.otf"):
                p = ASSETS / "Kalam-Bold.otf"; p.write_bytes(z.read(n))
                if _valid(p):
                    print("  handwriting font ready (Kalam, from release zip)"); _hand = p; return p
    except Exception:
        pass
    print("  handwriting font could not be downloaded; using the bundled Poppins instead")
    _hand = SANS
    return SANS


def font(kind, size):
    key = (kind, size)
    if key not in _cache:
        path = {"hand": hand_path, "mono": lambda: MONO, "sans": lambda: SANS}[kind]()
        _cache[key] = ImageFont.truetype(str(path), size)
    return _cache[key]


def emoji_font():
    if "emoji" not in _cache:
        _cache["emoji"] = ImageFont.truetype(str(EMOJI), 109)
    return _cache["emoji"]
