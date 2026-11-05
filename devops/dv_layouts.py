"""Scene layouts: turn a scene description into timed drawing elements.
Items appear when their `cue` words are spoken (position of the words in the narration), so picture and voice stay in sync."""
import math
from dv_anim import W, H, INK

PAL = [(0, 165, 168), (245, 138, 60), (47, 111, 219), (224, 74, 74), (46, 173, 107), (232, 170, 20)]
FILL = [(214, 241, 242), (253, 232, 212), (215, 228, 250), (251, 219, 219), (215, 241, 226), (255, 240, 200)]
GREY = (110, 115, 128)


def T(x, y, text, size=40, color=INK, at=0.0, dur=0.7, anchor="mm", maxw=1100, font="hand", align=None):
    return {"t": "text", "x": x, "y": y, "text": text, "size": size, "color": color, "at": at, "dur": dur,
            "anchor": anchor, "maxw": maxw, "font": font, "align": align}


def E(x, y, e, size, at, dur=0.5):
    return {"t": "emoji", "x": x, "y": y, "e": e or "🔹", "size": size, "at": at, "dur": dur}


def ICO(x, y, it, size, at, dur=0.5):
    """the item's real logo when it has one, otherwise its emoji"""
    if it.get("logo"):
        return {"t": "logo", "x": x, "y": y, "name": it["logo"], "size": size, "at": at, "dur": dur}
    return E(x, y, it.get("emoji"), size, at, dur)


def C(x, y, w, h, fill, at, dur=0.4, outline=INK, r=22, shape="rect", ow=4, alpha=255, noshadow=False):
    return {"t": "card", "x": x, "y": y, "w": w, "h": h, "fill": fill, "outline": outline, "r": r, "shape": shape,
            "ow": ow, "alpha": alpha, "at": at, "dur": dur, "noshadow": noshadow}


def A(p0, p1, at, dur=0.55, color=INK, width=7, bend=0.0):
    return {"t": "arrow", "p0": p0, "p1": p1, "at": at, "dur": dur, "color": color, "width": width, "bend": bend}


def R(x0, x1, y, at, color):
    return {"t": "rule", "x0": x0, "x1": x1, "y": y, "at": at, "dur": 0.6, "color": color}


def cue_time(narr, cue, D, i, n, lo=0.12, hi=0.88):
    """seconds at which item i of n should appear"""
    pos = narr.lower().find(str(cue).lower().strip()) if cue else -1
    frac = pos / max(len(narr), 1) if pos >= 0 else lo + (hi - lo) * (i + 0.5) / max(n, 1)
    return max(0.45, min(D - 0.9, frac * D * 0.97 - 0.2))


def heading(sc):
    return [T(W / 2, 64, sc["heading"], 56, INK, 0.1, 0.8, maxw=1120), R(W / 2 - 190, W / 2 + 190, 112, 0.6, PAL[1])]


def xs(n, gap):
    return [W / 2 + (i - (n - 1) / 2) * gap for i in range(n)]


# ------------------------------------------------------------------ layouts
def lay_definition(sc, D):
    n = sc["narration"]
    t1 = cue_time(n, sc.get("term"), D, 0, 3)
    return heading(sc) + [
        ICO(330, 400, sc, 270, 0.4, 0.6),
        T(840, 300, sc["term"], 92, PAL[2], t1, 0.8, maxw=600),
        R(600, 1090, 372, t1 + 0.5, PAL[1]),
        T(840, 480, sc["text"], 42, INK, cue_time(n, sc.get("text_cue"), D, 1, 3, 0.35, 0.8), 1.0, maxw=580),
    ]


def lay_icons(sc, D):
    items, n = sc["items"], sc["narration"]
    k = len(items)
    two = k > 4
    per = math.ceil(k / 2) if two else k
    out = heading(sc)
    for i, it in enumerate(items):
        row, col = (i // per, i % per) if two else (0, i)
        cnt = per if (not two or row == 0) else k - per
        gap = min(300, 1100 / max(cnt, 1))
        x = xs(cnt, gap)[col]
        y = (330 + row * 215) if two else 370
        size = 120 if two else 160
        t = cue_time(n, it.get("cue"), D, i, k)
        out += [ICO(x, y, it, size, t), T(x, y + size / 2 + 38, it["label"], 36, INK, t + 0.25, 0.5, maxw=gap - 16)]
    return out


def lay_flow(sc, D):
    items, n = sc["items"], sc["narration"]
    k = len(items)
    two = k > 4
    per = math.ceil(k / 2) if two else k
    cw, chh = (200, 210) if not two else (210, 190)
    out = heading(sc)
    pos = []
    for i, it in enumerate(items):
        row, col = (i // per, i % per) if two else (0, i)
        cnt = per if (not two or row == 0) else k - per
        gap = min(290, 1130 / max(cnt, 1))
        x = xs(cnt, gap)[col]
        y = (285 + row * 245) if two else 385
        pos.append((x, y))
        t = cue_time(n, it.get("cue"), D, i, k)
        out += [C(x, y, cw, chh, FILL[i % 6], t), ICO(x, y - 30, it, 92 if not two else 80, t + 0.12),
                T(x, y + 62, it["label"], 32, INK, t + 0.3, 0.5, maxw=cw - 14)]
        if i > 0:
            (px, py), same_row = pos[i - 1], (pos[i - 1][1] == y)
            if same_row:
                out.append(A((px + cw / 2 + 10, py), (x - cw / 2 - 10, y), t - 0.05, 0.4))
            else:  # return line from the end of row 1 to the start of row 2
                out.append(A((px, py + chh / 2 + 8), (x, y - chh / 2 - 8), t - 0.05, 0.6, bend=-0.22))
    return out


def lay_compare(sc, D):
    L, Rt, n = sc["left"], sc["right"], sc["narration"]
    out = heading(sc)
    for side, data, cx in ((0, L, 330), (1, Rt, 950)):
        style = data.get("style", "neutral")
        fill = (251, 226, 226) if style == "bad" else (214, 241, 226) if style == "good" else FILL[0 if side == 0 else 2]
        base = 0.08 if side == 0 else 0.5
        out += [C(cx, 410, 520, 450, fill, base * D, 0.45, r=28),
                E(cx - 150, 245, data.get("emoji", "🔹"), 74, base * D + 0.2),
                T(cx + 30, 245, data["title"], 44, INK, base * D + 0.3, 0.6, maxw=330)]
        pts = data["points"]
        for j, p in enumerate(pts):
            t = cue_time(n, data.get("cues", [None] * 9)[j] if isinstance(data.get("cues"), list) and j < len(data["cues"]) else None, D, j, len(pts),
                         0.14 + 0.42 * side, 0.46 + 0.42 * side)
            icon = "❌" if style == "bad" else "✅" if style == "good" else "🔹"
            out += [E(cx - 215, 330 + j * 72, icon, 40, t), T(cx - 180, 330 + j * 72, p, 32, INK, t + 0.15, 0.5, anchor="lm", maxw=390, align="left")]
    out += [C(W / 2, 410, 84, 84, PAL[1], 0.3 * D, 0.4, shape="circle"), T(W / 2, 410, "VS", 40, (255, 255, 255), 0.3 * D + 0.1, 0.3, font="sans")]
    return out


def lay_cycle(sc, D):
    items, n = sc["items"], sc["narration"]
    k = len(items)
    cx, cy, rx, ry = W / 2, 395, 420, 185
    out = heading(sc)
    pts = []
    for i, it in enumerate(items):
        a = -math.pi / 2 + 2 * math.pi * i / k
        x, y = cx + rx * math.cos(a), cy + ry * math.sin(a)
        pts.append((x, y))
        t = cue_time(n, it.get("cue"), D, i, k)
        out += [C(x, y, 120, 120, FILL[i % 6], t, shape="circle"), ICO(x, y, it, 70, t + 0.1),
                T(x, y + 86, it["label"], 30, INK, t + 0.3, 0.5, maxw=200)]
    for i in range(k):
        (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % k]
        d = math.hypot(x1 - x0, y1 - y0) or 1
        ux, uy = (x1 - x0) / d, (y1 - y0) / d
        t = cue_time(n, items[(i + 1) % k].get("cue"), D, i + 1, k) - 0.3
        out.append(A((x0 + ux * 74, y0 + uy * 74), (x1 - ux * 74, y1 - uy * 74), max(0.4, t), 0.45, bend=0.12, width=6))
    if sc.get("center"):
        out.append(T(cx, cy, sc["center"], 62, PAL[2], 0.5, 0.8, maxw=300))
    return out


def lay_list(sc, D):
    items, n = sc["items"], sc["narration"]
    k = len(items)
    step = min(112, 470 / max(k, 1))
    out = heading(sc)
    for i, it in enumerate(items):
        y = 205 + i * step + step / 2 - 20
        t = cue_time(n, it.get("cue"), D, i, k)
        out += [ICO(300, y, it, 78, t), T(390, y - (16 if it.get("detail") else 0), it["label"], 46, INK, t + 0.2, 0.6, anchor="lm", maxw=760, align="left")]
        if it.get("detail"):
            out.append(T(390, y + 32, it["detail"], 30, GREY, t + 0.5, 0.6, anchor="lm", maxw=760, align="left"))
    return out


def lay_stack(sc, D):
    items, n = sc["items"], sc["narration"]
    k = len(items)
    bh = min(112, 500 / k - 12)
    top = 410 - (k * (bh + 12)) / 2 + 20
    out = heading(sc)
    for i, it in enumerate(items):               # items are listed bottom -> top
        y = top + (k - 1 - i) * (bh + 12) + bh / 2
        t = cue_time(n, it.get("cue"), D, i, k)
        out += [C(W / 2, y, 900, bh, FILL[i % 6], t), ICO(W / 2 - 380, y, it, 64, t + 0.1),
                T(W / 2 + 40, y, it["label"], 40, INK, t + 0.25, 0.6, maxw=720)]
    return out


def lay_code(sc, D):
    lines = sc["lines"][:8]
    out = heading(sc)
    t0 = 0.8
    chars = sum(len(l) for l in lines)
    dur = max(1.5, min(D * 0.6, chars / 20))
    out += [C(W / 2, 372, 1000, 400, (30, 34, 46), 0.3, 0.5, r=20, ow=5)]
    for i, c in enumerate([(240, 90, 90), (245, 190, 60), (80, 200, 110)]):
        out.append(C(W / 2 - 470 + i * 38, 198, 22, 22, c, 0.5, 0.2, outline=None, shape="circle", noshadow=True))
    out.append({"t": "typed", "x": W / 2 - 450, "y": 235, "lines": lines, "size": 33, "at": t0, "dur": dur})
    if sc.get("caption"):
        out.append(T(W / 2, 640, sc["caption"], 40, PAL[2], min(D - 1.2, t0 + dur + 0.2), 0.7, maxw=1100))
    return out


def lay_quiz(sc, D):
    opts, ans, n = sc["options"], sc["answer"], sc["narration"]
    out = [T(W / 2, 62, "Quick Quiz!", 56, PAL[1], 0.1, 0.7), R(W / 2 - 170, W / 2 + 170, 112, 0.6, PAL[0]),
           E(120, 200, "🤔", 96, 0.3), T(W / 2 + 40, 195, sc["question"], 44, INK, 0.6, 1.0, maxw=1000)]
    pos = [(350, 370), (930, 370), (350, 540), (930, 540)]
    for i, o in enumerate(opts[:4]):
        x, y = pos[i]
        t = cue_time(n, None, D, i, 4, 0.2, 0.55)
        out += [C(x, y, 540, 128, FILL[i % 6], t),
                C(x - 220, y, 64, 64, PAL[i % 6], t + 0.05, 0.3, shape="circle", noshadow=True),
                T(x - 220, y, "ABCD"[i], 38, (255, 255, 255), t + 0.1, 0.3, font="sans"),
                T(x + 30, y, o, 34, INK, t + 0.2, 0.5, maxw=400)]
    tr = max(D * 0.74, D - 4.5)
    for i in range(min(4, len(opts))):
        x, y = pos[i]
        if i == ans:
            out += [C(x, y, 540, 128, (190, 240, 205), tr, 0.4, outline=(40, 160, 90), ow=6),
                    C(x - 220, y, 64, 64, (40, 160, 90), tr, 0.3, shape="circle", noshadow=True),
                    T(x - 220, y, "ABCD"[i], 38, (255, 255, 255), tr + 0.05, 0.3, font="sans"),
                    T(x + 30, y, opts[i], 34, INK, tr + 0.1, 0.4, maxw=400), E(x + 235, y, "✅", 64, tr + 0.2)]
        else:
            out.append(C(x, y, 540, 128, (253, 253, 253), tr, 0.4, outline=None, alpha=170, noshadow=True))
    return out


def lay_intro(sc, D):
    return [E(310, 385, sc["emoji"], 250, 0.3, 0.7),
            T(850, 215, sc["series"], 54, PAL[0], 0.5, 0.7, maxw=620),
            C(850, 300, 300, 66, PAL[1], 0.8, 0.4, r=20), T(850, 300, sc["episode"], 36, (255, 255, 255), 0.95, 0.4, font="sans"),
            T(850, 450, sc["title"], 76, INK, 1.2, 1.0, maxw=640)]


def lay_outro(sc, D):
    out = [T(W / 2, 105, "Thank you for watching!", 70, PAL[2], 0.3, 0.9)]
    for i, (e, lab) in enumerate([("👍", "Like"), ("🔔", "Subscribe"), ("📤", "Share")]):
        t = 1.0 + i * 0.7
        x = 320 + i * 320
        out += [E(x, 300, e, 130, t), T(x, 410, lab, 40, INK, t + 0.2, 0.5)]
    if sc.get("next"):
        out += [C(W / 2, 560, 960, 130, FILL[5], 3.2, 0.5, r=26), T(W / 2, 535, "Next episode", 32, GREY, 3.4, 0.5),
                T(W / 2, 590, sc["next"], 46, INK, 3.6, 0.8, maxw=900)]
    return out


BUILDERS = {"definition": lay_definition, "icons": lay_icons, "flow": lay_flow, "compare": lay_compare, "cycle": lay_cycle,
            "list": lay_list, "stack": lay_stack, "code": lay_code, "quiz": lay_quiz, "intro": lay_intro, "outro": lay_outro}


def build(scene, D):
    return BUILDERS[scene["layout"]](scene, D)
