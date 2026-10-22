"""Free AI images via Pollinations (no key). Falls back to the previous image if a request keeps failing."""
import random, time, urllib.parse, io, requests
from PIL import Image


def make_images(scenes, cfg, workdir):
    w, h = cfg["video"]["width"], cfg["video"]["height"]
    result, last = [], None
    for i, sc in enumerate(scenes):
        paths = []
        for j, prompt in enumerate(sc["image_prompts"]):
            path = workdir / f"img_{i:02d}_{j}.jpg"
            full = f"{prompt}. {cfg['image_style']}"
            url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(full) +
                   f"?width={w}&height={h}&nologo=true&model=flux&seed={random.randint(1, 10**6)}")
            ok = False
            for attempt in range(5):
                try:
                    r = requests.get(url, timeout=180)
                    r.raise_for_status()
                    Image.open(io.BytesIO(r.content)).convert("RGB").resize((w, h)).save(path, quality=92)
                    ok = True
                    break
                except Exception as e:
                    print(f"  image retry {attempt + 1}: {e}")
                    time.sleep(10 * (attempt + 1))
            if not ok:
                if last is None:
                    raise RuntimeError("First image failed; aborting")
                Image.open(last).save(path)
            last = path
            paths.append(str(path))
            time.sleep(4)  # be polite to the free service
        result.append(paths)
        print(f"  images for scene {i + 1}/{len(scenes)} done")
    return result
