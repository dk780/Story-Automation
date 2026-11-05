"""Whiteboard-explainer renderer. Elements (handwritten text, emoji icons, cards, arrows, typed code) appear on cue
with pop / wipe / draw-in animations. Everything is drawn with Pillow, so no browser or GPU is needed."""
import math
from PIL import Image, ImageDraw
import dv_fonts as F

W, H = 1280, 720
INK = (31, 36, 48)
BAR = [(245, 166, 35), (240, 102, 36), (33, 168, 90), (36, 140, 220)]
SS = 3  # supersampling for smooth shapes


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out(p):
    return 1 - (1 - p) ** 3


def ease_back(p, s=1.9):
    p = p - 1
    return 1 + (s + 1) * p ** 3 + s * p ** 2


def wrap(text, font, maxw):
    lines, cur = [], ""
    for w in str(text).split():
        t = (cur + " " + w).strip()
        if font.getlength(t) > maxw and cur:
            lines.append(cur); cur = w
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines or [""]


# ---------------- sprites ----------------
_emoji = {}


def emoji_sprite(e, _depth=0):
    if e in _emoji:
        return _emoji[e]
    tmp = Image.new("RGBA", (170, 170), (0, 0, 0, 0))
    try:
        ImageDraw.Draw(tmp).text((10, 10), e, font=F.emoji_font(), embedded_color=True)
    except Exception:
        pass
    bb = tmp.getbbox()
    if (not bb or bb[2] - bb[0] < 24) and _depth == 0:   # glyph missing in the font: use a neutral icon
        spr = emoji_sprite("🔹", 1)
    else:
        spr = tmp.crop(bb) if bb else tmp
    _emoji[e] = spr
    return spr


def text_sprite(el):
    font = F.font(el.get("font", "hand"), el["size"])
    asc, desc = font.getmetrics()
    lh = int((asc + desc) * el.get("lh", 1.0))
    lines = wrap(el["text"], font, el.get("maxw", 1100))
    w = int(max(font.getlength(l) for l in lines)) + 14
    h = lh * len(lines) + 8
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i, l in enumerate(lines):
        x = 7 if el.get("align") == "left" else (w - font.getlength(l)) / 2
        d.text((x, 4 + i * lh), l, font=font, fill=tuple(el.get("color", INK)) + (255,))
    return img


def shape_sprite(el):
    w, h, r = el["w"], el["h"], el.get("r", 22)
    pad, ow = 12, el.get("ow", 4)
    img = Image.new("RGBA", ((w + 2 * pad) * SS, (h + 2 * pad) * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    box = [pad * SS, pad * SS, (pad + w) * SS, (pad + h) * SS]
    sh = [box[0] + 4 * SS, box[1] + 6 * SS, box[2] + 4 * SS, box[3] + 6 * SS]
    fill = tuple(el["fill"]) + (el.get("alpha", 255),)
    out = tuple(el["outline"]) + (255,) if el.get("outline") else None
    if el.get("shape") == "circle":
        if not el.get("noshadow"):
            d.ellipse(sh, fill=(0, 0, 0, 38))
        d.ellipse(box, fill=fill, outline=out, width=ow * SS if out else 0)
    else:
        if not el.get("noshadow"):
            d.rounded_rectangle(sh, radius=r * SS, fill=(0, 0, 0, 38))
        d.rounded_rectangle(box, radius=r * SS, fill=fill, outline=out, width=ow * SS if out else 0)
    return img.resize((w + 2 * pad, h + 2 * pad), Image.LANCZOS)


def bezier(p0, p1, bend, n=56):
    mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy) or 1
    cx, cy = mx - dy / L * bend * L, my + dx / L * bend * L
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * cx + t * t * p1[0], (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * cy + t * t * p1[1])
            for t in [i / n for i in range(n + 1)]]


ARROW_STEPS = 12


def arrow_sprite(el, step):
    pts = bezier(el["p0"], el["p1"], el.get("bend", 0.0))
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    m = 34
    x0, y0 = int(min(xs)) - m, int(min(ys)) - m
    w, h = int(max(xs)) - x0 + m, int(max(ys)) - y0 + m
    img = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    col = tuple(el.get("color", INK)) + (255,)
    wd = el.get("width", 7)
    k = max(2, int(step / ARROW_STEPS * (len(pts) - 1)) + 1)
    seg = [((x - x0) * SS, (y - y0) * SS) for x, y in pts[:k]]
    d.line(seg, fill=col, width=wd * SS, joint="curve")
    for (x, y) in (seg[0], seg[-1]):
        d.ellipse([x - wd * SS / 2, y - wd * SS / 2, x + wd * SS / 2, y + wd * SS / 2], fill=col)
    if step >= ARROW_STEPS:  # open arrow head, like a marker drawing
        ex, ey = seg[-1]
        bx, by = seg[max(0, len(seg) - 7)]
        ang = math.atan2(ey - by, ex - bx)
        for s in (-0.5, 0.5):
            a = ang + math.pi + s
            d.line([(ex, ey), (ex + math.cos(a) * 30 * SS, ey + math.sin(a) * 30 * SS)], fill=col, width=wd * SS, joint="curve")
            cx, cy = ex + math.cos(a) * 30 * SS, ey + math.sin(a) * 30 * SS
            d.ellipse([cx - wd * SS / 2, cy - wd * SS / 2, cx + wd * SS / 2, cy + wd * SS / 2], fill=col)
    return img.resize((w, h), Image.LANCZOS), (x0, y0)


def rule_sprite(el):
    L = int(el["x1"] - el["x0"])
    img = Image.new("RGBA", (L * SS, 26 * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pts = [(i * SS, (13 + 3 * math.sin(i / 38.0)) * SS) for i in range(0, L, 4)]
    d.line(pts, fill=tuple(el.get("color", INK)) + (255,), width=6 * SS, joint="curve")
    return img.resize((L, 26), Image.LANCZOS)


# ---------------- compositor ----------------
def make_bg(channel):
    img = Image.new("RGB", (W, H), (253, 253, 253))
    d = ImageDraw.Draw(img)
    seg = W // len(BAR)
    for i, c in enumerate(BAR):
        d.rectangle([i * seg, 0, (i + 1) * seg, 8], fill=c)
    if channel:
        f = F.font("sans", 22)
        d.text((W - 24 - f.getlength(channel), H - 44), channel, font=f, fill=(190, 190, 196))
    return img


class SceneRenderer:
    def __init__(self, elements, duration, channel="", t0=0.0, total=1.0):
        self.els = []
        for z, e in enumerate(elements):
            e = dict(e); e["z"] = z; e["end"] = e["at"] + e.get("dur", 0.5)
            self.els.append(e)
        self.D, self.t0, self.total = duration, t0, max(total, 1.0)
        self.bg = make_bg(channel)
        self.static, self.done_key = self.bg.copy(), ()
        self.sp = {}

    # --- one element at progress p (0..1) onto img ---
    def draw(self, img, e, p):
        t = e["t"]
        if t == "typed":
            return self._typed(img, e, p)
        key = (e["z"], "base")
        if t == "arrow":
            step = int(round(clamp(p) * ARROW_STEPS))
            if step <= 0:
                return
            k = (e["z"], step)
            if k not in self.sp:
                self.sp[k] = arrow_sprite(e, step)
            spr, (x, y) = self.sp[k]
            img.paste(spr, (x, y), spr)
            return
        if key not in self.sp:
            self.sp[key] = {"text": text_sprite, "card": shape_sprite, "rule": rule_sprite}.get(t, lambda _: emoji_sprite(e["e"]))(e)
        spr = self.sp[key]
        if t == "text":
            w, h = spr.size
            x = {"mm": e["x"] - w / 2, "lm": e["x"] - 4, "rm": e["x"] - w + 4}[e.get("anchor", "mm")]
            y = e["y"] - h / 2
            vis = int(w * ease_out(clamp(p)))
            if vis > 0:
                crop = spr.crop((0, 0, vis, h))
                img.paste(crop, (int(x), int(y)), crop)
        elif t == "rule":
            L = spr.size[0]
            vis = int(L * ease_out(clamp(p)))
            if vis > 0:
                crop = spr.crop((0, 0, vis, spr.size[1]))
                img.paste(crop, (int(e["x0"]), int(e["y"] - 13)), crop)
        else:  # emoji / card: pop
            s = ease_back(clamp(p)) if t == "emoji" else 0.85 + 0.15 * ease_out(clamp(p))
            if t == "emoji":
                bw, bh = spr.size
                f = e["size"] / max(bw, bh)
                size = (max(1, int(bw * f * s)), max(1, int(bh * f * s)))
            else:
                size = (max(1, int(spr.size[0] * s)), max(1, int(spr.size[1] * s)))
            im = spr.resize(size, Image.LANCZOS if p >= 1 else Image.BILINEAR)
            a = clamp(p * 5)
            if a < 1:
                im = im.copy(); im.putalpha(im.getchannel("A").point(lambda v: int(v * a)))
            img.paste(im, (int(e["x"] - size[0] / 2), int(e["y"] - size[1] / 2)), im)

    def _typed(self, img, e, p):
        d = ImageDraw.Draw(img)
        f = F.font("mono", e["size"])
        total = sum(len(l) for l in e["lines"])
        n = int(total * clamp(p))
        y = e["y"]
        for l in e["lines"]:
            part = l[:max(0, n)]
            n -= len(l)
            col = (120, 220, 140) if l.startswith("$") else (225, 230, 240)
            d.text((e["x"], y), part, font=f, fill=col)
            y += int(e["size"] * 1.55)
            if n < 0:
                break
        if clamp(p) < 1 and int(p * 40) % 2 == 0:   # blinking cursor
            d.rectangle([e["x"] + f.getlength(part) + 3, y - int(e["size"] * 1.55) + 4, e["x"] + f.getlength(part) + 14, y - 8], fill=(235, 235, 235))

    def frame(self, t):
        fin = tuple(e["z"] for e in self.els if t >= e["end"])
        if fin != self.done_key:   # rebuild the static layer only when another element has finished
            self.static = self.bg.copy()
            for e in self.els:
                if e["z"] in fin:
                    self.draw(self.static, e, 1.0)
            self.done_key = fin
        img = self.static.copy()
        for e in self.els:
            if e["at"] <= t < e["end"]:
                self.draw(img, e, (t - e["at"]) / max(e.get("dur", 0.5), 1e-3))
        # slim progress bar along the bottom
        d = ImageDraw.Draw(img)
        d.rectangle([0, H - 6, int(W * clamp((self.t0 + t) / self.total)), H], fill=(36, 140, 220))
        edge = min(clamp(t / 0.18), clamp((self.D - t) / 0.25))   # soft fade in / out between scenes
        if edge < 1:
            img = Image.blend(Image.new("RGB", (W, H), (253, 253, 253)), img, edge)
        return img


def thumbnail(title, emoji, ep_label, channel, out_path):
    img = Image.new("RGB", (W, H), (253, 253, 253))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 18, H], fill=(36, 140, 220))
    seg = W // 4
    for i, c in enumerate(BAR):
        d.rectangle([i * seg, 0, (i + 1) * seg, 16], fill=c)
    spr = emoji_sprite(emoji)
    f = 380 / max(spr.size)
    big = spr.resize((int(spr.size[0] * f), int(spr.size[1] * f)), Image.LANCZOS)
    img.paste(big, (80, (H - big.size[1]) // 2 + 20), big)
    badge = Image.new("RGBA", (330, 80), (0, 0, 0, 0))
    ImageDraw.Draw(badge).rounded_rectangle([0, 0, 329, 79], radius=24, fill=(240, 102, 36, 255))
    fb = F.font("sans", 40)
    ImageDraw.Draw(badge).text((165 - fb.getlength(ep_label) / 2, 14), ep_label, font=fb, fill="white")
    img.paste(badge, (520, 110), badge)
    ft = F.font("hand", 104)
    y = 220
    for line in wrap(title, ft, 700)[:3]:
        d.text((520, y), line, font=ft, fill=INK)
        y += int(sum(ft.getmetrics()) * 0.98)
    fc = F.font("sans", 30)
    d.text((520, H - 70), channel, font=fc, fill=(36, 140, 220))
    img.save(out_path, quality=92)
