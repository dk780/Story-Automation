"""Pictures for the shots. Tries free AI providers in order; a provider that cannot work (bad key, no credits, endpoint gone)
is switched off for the run. If every provider fails for a picture, the previous picture is reused, so the video always completes."""
import base64, hashlib, io, os, random, time, urllib.parse
import requests
from PIL import Image, ImageDraw, ImageFilter, ImageOps


class Disable(Exception):
    """Provider cannot work in this run (missing key, no credits, endpoint gone)."""


def _check(r):
    if r.status_code in (401, 402, 403, 404, 410) or (r.status_code == 429 and "allocation" in r.text.lower()):
        raise Disable(f"HTTP {r.status_code}: {r.text[:120]}")
    r.raise_for_status()  # 400 / 429 / 5xx count as an ordinary failure of this one picture
    return r


def pollinations(prompt, w, h, cfg):
    key = os.environ.get("POLLINATIONS_API_KEY", "").strip()
    url = "https://gen.pollinations.ai/image/" + urllib.parse.quote(prompt)
    params = {"width": w, "height": h, "model": cfg["pollinations_model"], "nologo": "true", "seed": random.randint(1, 10**6)}
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    return _check(requests.get(url, params=params, headers=headers, timeout=90)).content


def cloudflare(prompt, w, h, cfg):
    acc, tok = os.environ.get("CF_ACCOUNT_ID", "").strip(), os.environ.get("CF_API_TOKEN", "").strip()
    if not acc or not tok:
        raise Disable("CF_ACCOUNT_ID / CF_API_TOKEN not set")
    url = f"https://api.cloudflare.com/client/v4/accounts/{acc}/ai/run/@cf/black-forest-labs/flux-1-schnell"
    r = _check(requests.post(url, headers={"Authorization": f"Bearer {tok}"}, json={"prompt": prompt[:2000], "steps": 4}, timeout=120))
    b64 = (r.json().get("result") or {}).get("image")
    if not b64:
        raise ValueError("no image in Cloudflare response")
    return base64.b64decode(b64)


def huggingface(prompt, w, h, cfg):
    token = os.environ.get("HF_TOKEN", "").strip()
    if not token:
        raise Disable("HF_TOKEN not set")
    url = f"https://router.huggingface.co/hf-inference/models/{cfg['hf_model']}"
    r = requests.post(url, headers={"Authorization": f"Bearer {token}"},
                      json={"inputs": prompt, "parameters": {"width": w, "height": h}}, timeout=120)
    return _check(r).content


PROVIDERS = {"pollinations": pollinations, "cloudflare": cloudflare, "huggingface": huggingface}


def placeholder(prompt, w, h, path):
    """Last resort (only when nothing was ever generated): a soft gradient coloured from the prompt text."""
    rnd = random.Random(int(hashlib.md5(prompt.encode()).hexdigest(), 16))
    col = lambda lo=40, hi=200: tuple(rnd.randint(lo, hi) for _ in range(3))
    top, bottom = col(20, 120), col(80, 230)
    img = Image.new("RGB", (w, h)); px = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        px.line([(0, y), (w, y)], fill=tuple(int(top[c] * (1 - t) + bottom[c] * t) for c in range(3)))
    glow = Image.new("RGB", (w, h)); gd = ImageDraw.Draw(glow)
    for _ in range(9):
        r, x, y = rnd.randint(80, 260), rnd.randint(0, w), rnd.randint(0, h)
        gd.ellipse([x - r, y - r, x + r, y + r], fill=col(90, 255))
    Image.blend(img, glow.filter(ImageFilter.GaussianBlur(70)), 0.45).save(path, quality=90)


def make_images(scenes, cfg, workdir):
    gw, gh = cfg["image_gen_size"]
    order = [p for p in cfg["image_providers"] if p in PROVIDERS]
    dead, fails = set(), {p: 0 for p in order}
    used = {p: 0 for p in order}; used["reused_previous"] = 0; used["placeholder"] = 0
    last, result = None, []
    for si, sc in enumerate(scenes):
        row = []
        for ki, shot in enumerate(sc["shots"]):
            prompt = shot.get("image_prompt")
            if not prompt and last:
                row.append(last); continue  # same picture, new camera move
            path = workdir / f"img_{si:02d}_{ki:02d}.jpg"
            if path.exists() and path.stat().st_size > 5000:  # resume
                last = str(path); row.append(last); continue
            full = f"{(prompt or 'epic scene').strip()} {cfg['image_style']}".strip()
            done = False
            for name in order:
                if name in dead:
                    continue
                for attempt in range(2):
                    try:
                        data = PROVIDERS[name](full, gw, gh, cfg)
                        ImageOps.fit(Image.open(io.BytesIO(data)).convert("RGB"), (gw, gh), Image.LANCZOS).save(path, quality=93)
                        fails[name], done = 0, True
                        used[name] += 1
                        break
                    except Disable as e:
                        print(f"  {name} switched off for this run: {e}")
                        dead.add(name); break
                    except Exception as e:
                        print(f"  {name} retry {attempt + 1}: {str(e)[:100]}")
                        time.sleep(6 * (attempt + 1))
                if done:
                    break
                if name not in dead:
                    fails[name] += 1
                    if fails[name] >= 3:
                        print(f"  {name} failed 3 pictures in a row; switched off for this run")
                        dead.add(name)
            if not done:
                if last:
                    path = last; used["reused_previous"] += 1
                else:
                    placeholder(full, gw, gh, path); used["placeholder"] += 1
            last = str(path); row.append(last)
            time.sleep(1)
        result.append(row)
        print(f"  pictures for scene {si + 1}/{len(scenes)} ready")
    print("  picture sources used:", used)
    if used["reused_previous"] + used["placeholder"] > 8:
        print("  WARNING: many pictures could not be generated. Check the image keys/credits in the secrets.")
    return result
