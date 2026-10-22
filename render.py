"""Assemble the video with ffmpeg: slow zoom (Ken Burns) on every image, narration, optional quiet music."""
import glob, random, subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, features


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def render(audio_files, image_groups, cfg, workdir, out_path):
    w, h, fps = cfg["video"]["width"], cfg["video"]["height"], cfg["video"]["fps"]
    padded, segs, idx = [], [], 0
    for i, (a, imgs) in enumerate(zip(audio_files, image_groups)):
        p = workdir / f"pad_{i:02d}.m4a"
        run(["ffmpeg", "-y", "-i", a, "-af", "apad=pad_dur=0.6", "-ar", "44100", "-ac", "2", "-c:a", "aac", str(p)])
        padded.append(p)
        per = duration(p) / len(imgs)
        for img in imgs:
            frames = max(int(per * fps), 1)
            inc = 0.2 / frames
            z = f"min(zoom+{inc:.7f},1.2)" if idx % 2 == 0 else f"if(eq(on,0),1.2,max(zoom-{inc:.7f},1.0))"
            vf = (f"scale=1920:-2,zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                  f":d={frames}:s={w}x{h}:fps={fps},format=yuv420p")
            seg = workdir / f"seg_{idx:03d}.mp4"
            run(["ffmpeg", "-y", "-i", img, "-vf", vf, "-frames:v", str(frames), "-c:v", "libx264",
                 "-preset", "veryfast", "-crf", "23", str(seg)])
            segs.append(seg)
            idx += 1
        print(f"  rendered scene {i + 1}/{len(audio_files)}")

    def concat(files, name, extra):
        lst = workdir / f"{name}.txt"
        lst.write_text("".join(f"file '{Path(f).resolve()}'\n" for f in files))
        out = workdir / f"{name}_all{extra}"
        run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)])
        return out

    video, audio = concat(segs, "v", ".mp4"), concat(padded, "a", ".m4a")
    music = sorted(glob.glob("assets/music/*.mp3"))
    if music:  # optional: drop royalty-free .mp3 files into assets/music/
        run(["ffmpeg", "-y", "-i", str(video), "-i", str(audio), "-stream_loop", "-1", "-i", random.choice(music),
             "-filter_complex", "[2:a]volume=0.07[m];[1:a][m]amix=inputs=2:duration=first:dropout_transition=0[a]",
             "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-shortest", str(out_path)])
    else:
        run(["ffmpeg", "-y", "-i", str(video), "-i", str(audio), "-c:v", "copy", "-c:a", "aac", "-shortest", str(out_path)])
    return duration(out_path)


def make_thumbnail(first_image, title, cfg, out_path):
    img = Image.open(first_image).convert("RGB").resize((1280, 720))
    if features.check("raqm") or cfg["language"] == "english":  # raqm is needed to shape Devanagari correctly
        try:
            font = ImageFont.truetype(cfg["thumbnail_font"], 84)
            overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            d = ImageDraw.Draw(overlay)
            d.rectangle([0, 420, 1280, 720], fill=(0, 0, 0, 150))
            words, lines, cur = title.split(), [], ""
            for wd in words:
                if len(cur + " " + wd) > 22 and cur:
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
