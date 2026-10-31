"""Builds the video: one shot per narrated sentence, each with its own camera move and caption, dissolves between shots,
narration + background music that ducks under the voice."""
import glob, random, re, shutil, subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, features, ImageOps
try:
    import numpy as np, cv2
except Exception:  # simple zoom/pan mode still works without them
    np = cv2 = None


def _find_ffmpeg():
    found = shutil.which("ffmpeg")
    if found:
        return found
    import imageio_ffmpeg  # static ffmpeg bundled in a pip package
    return imageio_ffmpeg.get_ffmpeg_exe()


FFMPEG = _find_ffmpeg()


def run(cmd):
    cmd = [FFMPEG if c == "ffmpeg" else c for c in cmd]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        print("ffmpeg failed:", e.stderr.decode(errors="replace")[-1500:])
        raise


def duration(path):
    probe = shutil.which("ffprobe")
    if probe:
        out = subprocess.run([probe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                             capture_output=True, text=True, check=True).stdout
        return float(out.strip())
    err = subprocess.run([FFMPEG, "-i", str(path)], capture_output=True, text=True).stderr
    h, m, s = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", err).groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


# ---------- camera moves ----------
MOVES = ["zoom_in", "zoom_out", "pan_right", "pan_left", "tilt_up", "zoom_in_left", "zoom_in_right", "tilt_down"]


def move_filter(kind, frames, w, h, fps):
    n = max(frames, 2)
    cx, cy = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    z, x, y = {
        "zoom_in": (f"1+0.22*on/{n}", cx, cy),
        "zoom_out": (f"1.22-0.22*on/{n}", cx, cy),
        "pan_right": ("1.2", f"(iw-iw/zoom)*on/{n}", cy),
        "pan_left": ("1.2", f"(iw-iw/zoom)*(1-on/{n})", cy),
        "tilt_up": ("1.2", cx, f"(ih-ih/zoom)*(1-on/{n})"),
        "tilt_down": ("1.2", cx, f"(ih-ih/zoom)*on/{n}"),
        "zoom_in_left": (f"1+0.25*on/{n}", "(iw-iw/zoom)*0.15", cy),
        "zoom_in_right": (f"1+0.25*on/{n}", "(iw-iw/zoom)*0.85", cy),
    }[kind]
    return f"scale=2560:-2,zoompan=z='{z}':x='{x}':y='{y}':d={n}:s={w}x{h}:fps={fps}"


# ---------- captions ----------
def captions_available(cfg):
    if not cfg.get("captions", True):
        return False
    if not Path(cfg["caption_font"]).exists():
        print("  captions off: font file missing:", cfg["caption_font"]); return False
    if cfg["language"] == "hindi" and not (features.check("raqm") and features.check("fribidi")):
        print("  captions off: this machine cannot shape Devanagari text (raqm/fribidi missing)"); return False
    return True


def caption_png(text, cfg, path, speaker=None, color=None, title=None):
    w, h = cfg["video"]["width"], cfg["video"]["height"]
    size = cfg.get("caption_size", 46)
    mk = lambda sz: ImageFont.truetype(cfg["caption_font"], sz, layout_engine=ImageFont.Layout.RAQM) \
        if features.check("raqm") else ImageFont.truetype(cfg["caption_font"], sz)
    font, small = mk(size), mk(int(size * 0.72))
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if font.getlength(trial) > w * 0.84 and cur:
            lines.append(cur); cur = word
        else:
            cur = trial
    lines.append(cur)
    lh = int(size * 1.5)
    box_w = int(max(font.getlength(l) for l in lines)) + 56
    box_h = lh * len(lines) + 26
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x0, y0 = (w - box_w) // 2, h - box_h - 46
    d.rounded_rectangle([x0, y0, x0 + box_w, y0 + box_h], radius=16, fill=(0, 0, 0, 160),
                        outline=(color or (255, 255, 255)) + (230,) if speaker else None, width=3 if speaker else 0)
    for i, line in enumerate(lines):
        tw = font.getlength(line)
        d.text(((w - tw) / 2, y0 + 10 + i * lh), line, font=font, fill="white", stroke_width=2, stroke_fill="black")
    if title:  # title banner on the opening shot
        big = mk(60)
        tl, cur = [], ""
        for word in title.split():
            trial = (cur + " " + word).strip()
            if big.getlength(trial) > w * 0.82 and cur:
                tl.append(cur); cur = word
            else:
                cur = trial
        tl.append(cur)
        bh = 84 * len(tl) + 24
        d.rounded_rectangle([60, 36, w - 60, 36 + bh], radius=22, fill=(0, 0, 0, 150), outline=(255, 205, 90, 255), width=3)
        for i, line in enumerate(tl[:3]):
            d.text(((w - big.getlength(line)) / 2, 48 + i * 84), line, font=big, fill=(255, 224, 140), stroke_width=3, stroke_fill=(60, 30, 0))
    if speaker:  # name tag of whoever is talking
        tw = small.getlength(speaker)
        cw, ch = int(tw) + 40, int(size * 0.72 * 1.5) + 6
        d.rounded_rectangle([x0 + 18, y0 - ch + 4, x0 + 18 + cw, y0 + 4], radius=12, fill=(color or (255, 170, 60)) + (255,))
        d.text((x0 + 38, y0 - ch + 6), speaker, font=small, fill=(20, 20, 20))
    img.save(path)


# ---------- 3D-style camera (depth parallax) ----------
CAMS = ["orbit_right", "orbit_left", "push_in", "pull_back", "rise", "drop"]


def _cam(kind, e):
    """-> (cam_x, cam_y, zoom, parallax_x) for eased progress e in 0..1"""
    sway = 0.7 * np.sin(np.pi * e)
    return {
        "orbit_right": (-1 + 2 * e, 0.0, 1.14, -1 + 2 * e),
        "orbit_left": (1 - 2 * e, 0.0, 1.14, 1 - 2 * e),
        "push_in": (0.25 * (e - .5), 0.0, 1.08 + 0.18 * e, sway),
        "pull_back": (0.25 * (e - .5), 0.0, 1.26 - 0.18 * e, -sway),
        "rise": (0.0, -1 + 2 * e, 1.14, 0.4 * sway),
        "drop": (0.0, 1 - 2 * e, 1.14, -0.4 * sway),
    }[kind]


def envelope(audio_path, fps, frames):
    """loudness of the voice per video frame (0..1), used to make the speaker bob while talking"""
    raw = subprocess.run([FFMPEG, "-v", "error", "-i", str(audio_path), "-ac", "1", "-ar", "8000", "-f", "f32le", "-"],
                         capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.float32)
    hop = max(int(8000 / fps), 1)
    n = len(x) // hop
    rms = np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(1)) if n else np.zeros(1)
    rms = rms / (np.percentile(rms, 95) + 1e-6)
    rms = np.clip(rms, 0, 1)
    rms = np.convolve(rms, np.ones(3) / 3, mode="same")          # smooth, so it moves like breath/speech not jitter
    out = np.zeros(frames, dtype=np.float32)
    out[:min(frames, len(rms))] = rms[:frames]
    return out


def make_particles(rnd, W, H, count=60):
    return [dict(x=rnd.uniform(0, W), y=rnd.uniform(0, H), vx=rnd.uniform(-8, 8), vy=-rnd.uniform(10, 38),
                 r=rnd.choice([1, 1, 2, 2, 3]), ph=rnd.uniform(0, 6.28), sp=rnd.uniform(1.0, 2.6)) for _ in range(count)]


def parallax_clip(img_path, depth, kind, frames, cfg, cap_png, env, talk, out):
    W, H, fps = cfg["video"]["width"], cfg["video"]["height"], cfg["video"]["fps"]
    img = cv2.imread(str(img_path))
    ih, iw = img.shape[:2]
    depth = cv2.resize(depth, (iw, ih)).astype(np.float32)
    xs = (np.arange(W, dtype=np.float32) + 0.5) / W
    ys = (np.arange(H, dtype=np.float32) + 0.5) / H
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    vig = np.repeat(((1 - 0.35 * (((xx / W - .5) ** 2 + (yy / H - .5) ** 2) * 2.2)) * 255).astype(np.uint8)[..., None], 3, axis=2)
    cmd = [FFMPEG, "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-"]
    if cap_png:
        cmd += ["-i", str(cap_png), "-filter_complex", "[0:v][1:v]overlay=0:0:format=auto,format=yuv420p[o]", "-map", "[o]"]
    else:
        cmd += ["-pix_fmt", "yuv420p"]
    cmd += ["-frames:v", str(frames), "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p", str(out)]
    errlog = open(str(out) + ".log", "wb")
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=errlog)
    PX, PY, S = 0.034 * iw, 0.028 * ih, 0.013 * ih
    parts = make_particles(random.Random(hash(str(img_path)) & 0xFFFF), W, H) if cfg.get("particles", True) else []
    try:
        for f in range(frames):
            p = f / max(frames - 1, 1)
            e = p * p * (3 - 2 * p)
            cx, cy, z, px = _cam(kind, e)
            a = float(env[f]) if f < len(env) else 0.0
            z = z * (1 + 0.007 * a * talk)
            ww, hh = iw / z, ih / z
            mx, my = (iw - ww) / 2 * 0.55, (ih - hh) / 2 * 0.55
            ccx, ccy = iw / 2 + cx * mx, ih / 2 + cy * my
            bx = np.broadcast_to((ccx - ww / 2 + xs * ww)[None, :], (H, W)).astype(np.float32)
            by = np.broadcast_to((ccy - hh / 2 + ys * hh)[:, None], (H, W)).astype(np.float32)
            dv = cv2.remap(depth, bx, by, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101) - 0.5
            breath = np.sin(2 * np.pi * f / (fps * 3.4)) * 0.0015 * ih
            mapx = (bx + px * PX * dv).astype(np.float32)
            mapy = (by + (cy * PY * dv) + (a * talk * S + breath) * (dv + 0.5) ** 2).astype(np.float32)   # near pixels bob while the voice is loud
            frame = cv2.remap(img, mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
            frame = cv2.multiply(frame, vig, scale=1 / 255.0)
            if parts:  # floating golden light dust, drawn on its own layer and added as a glow
                layer = np.zeros((H, W, 3), np.uint8)
                t = f / fps
                for q in parts:
                    px_, py_ = (q["x"] + q["vx"] * t) % W, (q["y"] + q["vy"] * t) % H
                    tw = 0.55 + 0.45 * np.sin(q["ph"] + t * q["sp"] * 2)
                    cv2.circle(layer, (int(px_), int(py_)), q["r"], (int(120 * tw), int(200 * tw), int(255 * tw)), -1, cv2.LINE_AA)
                glow = cv2.GaussianBlur(layer, (0, 0), 3)
                frame = cv2.add(frame, cv2.add(layer, glow))
            proc.stdin.write(frame.tobytes())
        proc.stdin.close()
        proc.wait()
    finally:
        errlog.close()
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd, stderr=Path(str(out) + ".log").read_bytes())


# ---------- main render ----------
def render(plan, cfg, workdir, out_path, mood=None):
    """plan: list of scenes; each scene is a list of shots {audio, image, text}."""
    w, h, fps = cfg["video"]["width"], cfg["video"]["height"], cfg["video"]["fps"]
    xf = cfg.get("crossfade", 0.5)
    xf_frames = int(round(xf * fps))
    xf = xf_frames / fps
    use_caps = captions_available(cfg)
    use_3d = cfg.get("animation", "parallax") == "parallax" and cv2 is not None
    if cfg.get("animation", "parallax") == "parallax" and cv2 is None:
        print("  OpenCV not installed: using simple zoom/pan instead of the 3D camera")
    if use_3d:
        import depth as depthmod
    rnd = random.Random(7)
    wavs, scene_files, prev_move, shot_no = [], [], None, 0

    for si, scene in enumerate(plan):
        clips, durs = [], []
        for ki, shot in enumerate(scene):
            pad = 0.7 if ki == len(scene) - 1 else 0.12           # a breath between scenes
            raw = duration(shot["audio"])
            frames = int(-(-(raw + pad) * fps // 1))               # whole frames, so picture and voice never drift
            d = frames / fps
            wav = workdir / f"w_{si:02d}_{ki:02d}.wav"
            fx = (shot.get("fx") + ",") if shot.get("fx") else ""
            run(["ffmpeg", "-y", "-i", shot["audio"], "-af", f"{fx}apad=whole_dur={d:.6f}", "-t", f"{d:.6f}",
                 "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(wav)])
            wavs.append(wav)
            total = frames + xf_frames                              # extra tail overlaps into the next shot
            clip = workdir / f"c_{si:02d}_{ki:02d}.mp4"
            png = None
            if use_caps:
                png = workdir / f"cap_{si:02d}_{ki:02d}.png"
                who = (shot.get("label") or shot.get("speaker")) if shot.get("speaker") and shot["speaker"] != "Narrator" else None
                caption_png(shot["text"], cfg, png, who, shot.get("color"), shot.get("title"))
            done = False
            if use_3d:
                try:
                    kind = rnd.choice([m for m in CAMS if m != prev_move]); prev_move = kind
                    dmap = depthmod.depth_for(shot["image"], cfg)
                    talk = cfg.get("talk_motion", 1.0) if (shot.get("speaker") and shot["speaker"] != "Narrator") else cfg.get("narrator_motion", 0.35)
                    parallax_clip(shot["image"], dmap, kind, total, cfg, png, envelope(shot["audio"], fps, total), talk, clip)
                    done = True
                except Exception as e:
                    print("  3D camera failed for a shot, using simple zoom:", str(e)[:200])
            if not done:
                kind = rnd.choice([m for m in MOVES if m != prev_move]); prev_move = kind
                chain = f"{move_filter(kind, total, w, h, fps)},format=yuv420p"
                cmd = ["ffmpeg", "-y", "-i", shot["image"]]
                if png:
                    cmd += ["-i", str(png), "-filter_complex", f"[0:v]{chain}[v];[v][1:v]overlay=0:0:format=auto,format=yuv420p[o]", "-map", "[o]"]
                else:
                    cmd += ["-vf", chain]
                cmd += ["-frames:v", str(total), "-r", str(fps), "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p", str(clip)]
                run(cmd)
            clips.append(clip); durs.append(d); shot_no += 1

        scene_out = workdir / f"scene_{si:02d}.mp4"
        sum_d = sum(durs)
        if len(clips) == 1:
            run(["ffmpeg", "-y", "-i", str(clips[0]), "-t", f"{sum_d:.6f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", str(scene_out)])
        else:
            cmd = ["ffmpeg", "-y"]
            for c in clips:
                cmd += ["-i", str(c)]
            parts, prev, acc = [], "[0:v]", 0.0
            for k in range(1, len(clips)):
                acc += durs[k - 1]
                lab = f"[x{k}]"
                parts.append(f"{prev}[{k}:v]xfade=transition=fade:duration={xf:.4f}:offset={acc:.4f}{lab}")
                prev = lab
            cmd += ["-filter_complex", ";".join(parts), "-map", prev, "-t", f"{sum_d:.6f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p", str(scene_out)]
            run(cmd)
        scene_files.append(scene_out)
        print(f"  rendered scene {si + 1}/{len(plan)} ({len(clips)} shots)")

    def concat(files, name, ext):
        lst = workdir / f"{name}.txt"
        lst.write_text("".join(f"file '{Path(f).resolve()}'\n" for f in files))
        out = workdir / f"{name}_all{ext}"
        run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)])
        return out

    video, voice = concat(scene_files, "v", ".mp4"), concat(wavs, "a", ".wav")
    total_t = duration(voice)
    tracks = sorted(glob.glob("assets/music/*.mp3"))
    mood_tracks = [t for t in tracks if mood and Path(t).stem == mood]
    track = mood_tracks[0] if mood_tracks else (random.choice(tracks) if tracks else None)
    if track:
        mv = cfg.get("music_volume", 0.3)
        fo = max(total_t - 3.0, 0)
        fc = (f"[1:a]asplit=2[v1][v2];[2:a]volume={mv}[m];"
              f"[m][v1]sidechaincompress=threshold=0.02:ratio=9:attack=20:release=350[duck];"
              f"[v2][duck]amix=inputs=2:duration=first:dropout_transition=0,volume=2,afade=t=out:st={fo:.2f}:d=3[a]")
        run(["ffmpeg", "-y", "-i", str(video), "-i", str(voice), "-stream_loop", "-1", "-i", track,
             "-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", f"{total_t:.3f}", str(out_path)])
    else:
        run(["ffmpeg", "-y", "-i", str(video), "-i", str(voice), "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", f"{total_t:.3f}", str(out_path)])
    return duration(out_path)


def make_thumbnail(first_image, title, cfg, out_path):
    img = ImageOps.fit(Image.open(first_image).convert("RGB"), (1280, 720))
    if features.check("raqm") or cfg["language"] == "english":
        try:
            font = ImageFont.truetype(cfg["thumbnail_font"], 84)
            overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            d = ImageDraw.Draw(overlay)
            d.rectangle([0, 420, 1280, 720], fill=(0, 0, 0, 150))
            lines, cur = [], ""
            for wd in title.split():
                if font.getlength((cur + " " + wd).strip()) > 1160 and cur:
                    lines.append(cur); cur = wd
                else:
                    cur = (cur + " " + wd).strip()
            lines.append(cur)
            for n, line in enumerate(lines[:3]):
                d.text((50, 440 + n * 95), line, font=font, fill="white", stroke_width=3, stroke_fill="black")
            img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        except Exception as e:
            print("  thumbnail text skipped:", e)
    img.save(out_path, quality=90)
