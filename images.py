"""Images that never block the video: try free AI providers, and fall back to generated artwork.
A provider that fails permanently (bad key, 404...) or keeps failing is switched off for the rest of the run."""
import hashlib, io, os, random, time, urllib.parse
import requests
from PIL import Image, ImageDraw, ImageFilter


class Disable(Exception):
    """Provider cannot work in this run (missing key, endpoint gone, auth error)."""


def _check(r):
    if r.status_code in (400, 401, 402, 403, 404, 410):
        raise Disable(f"HTTP {r.status_code}: {r.text[:120]}")
    r.raise_for_status()
    return r.content


def pollinations(prompt, w, h, cfg):
    key = os.environ.get("POLLINATIONS_API_KEY", "").strip()
    url = "https://gen.pollinations.ai/image/" + urllib.parse.quote(prompt)
    params = {"width": w, "height": h, "model": cfg["pollinations_model"], "nologo": "true", "seed": random.randint(1, 10**6)}
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    return _check(requests.get(url, params=params, headers=headers, timeout=90))


def huggingface(prompt, w, h, cfg):
    token = os.environ.get("HF_TOKEN", "").strip()
    if not token:
        raise Disable("HF_TOKEN not set")
    url = f"https://router.huggingface.co/hf-inference/models/{cfg['hf_model']}"
    r = requests.post(url, headers={"Authorization": f"Bearer {token}"},
                      json={"inputs": prompt, "parameters": {"width": w, "height": h}}, timeout=120)
    return _check(r)


PROVIDERS = {"pollinations": pollinations, "huggingface": huggingface}


def placeholder(prompt, w, h, path):
    """Always works: a soft, painterly gradient with glowing orbs, coloured from the prompt text."""
    rnd = random.Random(int(hashlib.md5(prompt.encode()).hexdigest(), 16))
    def col(lo=40, hi=200): return tuple(rnd.randint(lo, hi) for _ in range(3))
    top, bottom = col(20, 120), col(80, 230)
    img = Image.new("RGB", (w, h))
    px = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        px.line([(0, y), (w, y)], fill=tuple(int(top[c] * (1 - t) + bottom[c] * t) for c in range(3)))
    glow = Image.new("RGB", (w, h), (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for _ in range(9):
        r, x, y = rnd.randint(80, 260), rnd.randint(0, w), rnd.randint(0, h)
        gd.ellipse([x - r, y - r, x + r, y + r], fill=col(90, 255))
    glow = glow.filter(ImageFilter.GaussianBlur(70))
    Image.blend(img, Image.composite(glow, img, Image.new("L", (w, h), 255)), 0.45).save(path, quality=90)


def make_images(scenes, cfg, workdir):
    w, h = cfg["video"]["width"], cfg["video"]["height"]
    order = [p for p in cfg["image_providers"] if p in PROVIDERS]
    dead, fails, used = set(), {p: 0 for p in order}, {p: 0 for p in order}
    used["placeholder"] = 0
    result = []
    for i, sc in enumerate(scenes):
        paths = []
        for j, prompt in enumerate(sc["image_prompts"]):
            path = workdir / f"img_{i:02d}_{j}.jpg"
            if path.exists() and path.stat().st_size > 5000:  # resume
                paths.append(str(path)); continue
            full = f"{prompt.strip()} {cfg['image_style']}".strip()
            done = False
            for name in order:
                if name in dead:
                    continue
                for attempt in range(2):
                    try:
                        data = PROVIDERS[name](full, w, h, cfg)
                        Image.open(io.BytesIO(data)).convert("RGB").resize((w, h)).save(path, quality=92)
                        fails[name], done = 0, True
                        used[name] += 1
                        break
                    except Disable as e:
                        print(f"  {name} switched off for this run: {e}")
                        dead.add(name); break
                    except Exception as e:
                        print(f"  {name} retry {attempt + 1}: {str(e)[:100]}")
                        time.sleep(8 * (attempt + 1))
                if done:
                    break
                if name not in dead:
                    fails[name] += 1
                    if fails[name] >= 3:
                        print(f"  {name} failed 3 images in a row; switched off for this run")
                        dead.add(name)
            if not done:
                placeholder(full, w, h, path)
                used["placeholder"] += 1
            paths.append(str(path))
            time.sleep(2)
        result.append(paths)
        print(f"  images for scene {i + 1}/{len(scenes)} done")
    print("  image sources used:", used)
    if used["placeholder"] > len(scenes):
        print("  WARNING: many placeholder images. Set POLLINATIONS_API_KEY or HF_TOKEN for real AI images.")
    return result
