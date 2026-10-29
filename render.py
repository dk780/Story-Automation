"""Builds the video: one shot per narrated sentence, each with its own camera move and caption, dissolves between shots,
narration + background music that ducks under the voice."""
import glob, random, re, shutil, subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, features, ImageOps


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


def caption_png(text, cfg, path):
    w, h = cfg["video"]["width"], cfg["video"]["height"]
    size = cfg.get("caption_size", 46)
    font = ImageFont.truetype(cfg["caption_font"], size, layout_engine=ImageFont.Layout.RAQM) \
        if features.check("raqm") else ImageFont.truetype(cfg["caption_font"], size)
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
    d.rounded_rectangle([x0, y0, x0 + box_w, y0 + box_h], radius=16, fill=(0, 0, 0, 150))
    for i, line in enumerate(lines):
        tw = font.getlength(line)
        d.text(((w - tw) / 2, y0 + 10 + i * lh), line, font=font, fill="white", stroke_width=2, stroke_fill="black")
    img.save(path)


# ---------- main render ----------
def render(plan, cfg, workdir, out_path, mood=None):
    """plan: list of scenes; each scene is a list of shots {audio, image, text}."""
    w, h, fps = cfg["video"]["width"], cfg["video"]["height"], cfg["video"]["fps"]
    xf = cfg.get("crossfade", 0.5)
    xf_frames = int(round(xf * fps))
    xf = xf_frames / fps
    use_caps = captions_available(cfg)
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
            run(["ffmpeg", "-y", "-i", shot["audio"], "-af", f"apad=whole_dur={d:.6f}", "-t", f"{d:.6f}",
                 "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(wav)])
            wavs.append(wav)
            kind = rnd.choice([m for m in MOVES if m != prev_move]); prev_move = kind
            total = frames + xf_frames                              # extra tail overlaps into the next shot
            clip = workdir / f"c_{si:02d}_{ki:02d}.mp4"
            chain = f"{move_filter(kind, total, w, h, fps)},format=yuv420p"
            cmd = ["ffmpeg", "-y", "-i", shot["image"]]
            if use_caps:
                png = workdir / f"cap_{si:02d}_{ki:02d}.png"
                caption_png(shot["text"], cfg, png)
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
