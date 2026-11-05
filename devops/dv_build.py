"""Renders every scene to video (frames piped to ffmpeg), joins them with the narration and ducked background music."""
import glob, random, re, shutil, subprocess
from pathlib import Path
import dv_anim as A
import dv_layouts as L


def _ffmpeg():
    p = shutil.which("ffmpeg")
    if p:
        return p
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


FF = _ffmpeg()


def run(cmd):
    cmd = [FF if c == "ffmpeg" else c for c in cmd]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        print("ffmpeg failed:", e.stderr.decode(errors="replace")[-1200:])
        raise


def duration(path):
    err = subprocess.run([FF, "-i", str(path)], capture_output=True, text=True).stderr
    h, m, s = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", err).groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


def render_scene(elements, D, fps, channel, t0, total, out):
    r = A.SceneRenderer(elements, D, channel, t0, total)
    frames = int(round(D * fps))
    log = open(str(out) + ".log", "wb")
    p = subprocess.Popen([FF, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{A.W}x{A.H}", "-r", str(fps), "-i", "-",
                          "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(out)],
                         stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log)
    try:
        for f in range(frames):
            p.stdin.write(r.frame(f / fps).tobytes())
        p.stdin.close(); p.wait()
    finally:
        log.close()
    if p.returncode != 0:
        raise RuntimeError("ffmpeg failed while rendering a scene: " + Path(str(out) + ".log").read_text(errors="replace")[-600:])


def build(scenes, audio, cfg, work, out_path, music=None):
    """scenes: list of scene dicts (layout builders applied here); audio: mp3 per scene. Returns (seconds, chapter list)."""
    fps = cfg["video"]["fps"]
    durs, wavs = [], []
    for i, a in enumerate(audio):
        raw = duration(a)
        frames = int(-(-(raw + 0.55) * fps // 1))
        d = frames / fps
        w = work / f"w_{i:02d}.wav"
        run(["ffmpeg", "-y", "-i", a, "-af", f"apad=whole_dur={d:.6f}", "-t", f"{d:.6f}", "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(w)])
        durs.append(d); wavs.append(w)
    total, t0, files, chapters = sum(durs), 0.0, [], []
    for i, (sc, d) in enumerate(zip(scenes, durs)):
        out = work / f"scene_{i:02d}.mp4"
        if not (out.exists() and out.stat().st_size > 2000):     # resume: finished scenes are kept
            render_scene(L.build(sc, d), d, fps, cfg.get("channel_name", ""), t0, total, out)
        files.append(out)
        chapters.append((t0, "Intro" if sc["layout"] == "intro" else "Quiz" if sc["layout"] == "quiz" else "Wrap-up" if sc["layout"] == "outro" else sc["heading"]))
        t0 += d
        print(f"  rendered scene {i + 1}/{len(scenes)} ({sc['layout']}, {d:.0f}s)")

    def concat(fs, name, ext):
        lst = work / f"{name}.txt"
        lst.write_text("".join(f"file '{Path(f).resolve()}'\n" for f in fs))
        o = work / f"{name}_all{ext}"
        run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(o)])
        return o

    video, voice = concat(files, "v", ".mp4"), concat(wavs, "a", ".wav")
    tracks = sorted(glob.glob(str(Path(__file__).parent.parent / "assets" / "music" / "*.mp3")))
    pick = [t for t in tracks if music and Path(t).stem == music] or tracks
    base = ["ffmpeg", "-y", "-i", str(video), "-i", str(voice)]
    tail = ["-map", "0:v", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.3f}", str(out_path)]
    if pick:
        mv, fo = cfg.get("music_volume", 0.16), max(total - 3.0, 0)
        track = ["-stream_loop", "-1", "-i", pick[0]]
        duck = (f"[1:a]asplit=2[v1][v2];[2:a]volume={mv}[m];[m][v1]sidechaincompress=threshold=0.02:ratio=9:attack=20:release=350[duck];"
                f"[v2][duck]amix=inputs=2:duration=first:dropout_transition=0,volume=2,afade=t=out:st={fo:.2f}:d=3[a]")
        simple = f"[2:a]volume={mv}[m];[1:a][m]amix=inputs=2:duration=first:dropout_transition=0,volume=2,afade=t=out:st={fo:.2f}:d=3[a]"
        try:
            run(base + track + ["-filter_complex", duck, "-map", "[a]"] + tail)
        except Exception:
            print("  ducking filter unavailable, mixing music without it")
            run(base + track + ["-filter_complex", simple, "-map", "[a]"] + tail)
    else:
        run(base + ["-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.3f}", str(out_path)])
    return duration(out_path), chapters


def fmt(t):
    t = int(t)
    return f"{t // 60}:{t % 60:02d}"


def chapters_text(chapters):
    """YouTube chapters: first at 0:00, at least 3, each at least 10 seconds long"""
    out, last = [], -99
    for t, name in chapters:
        if t - last >= 10 or not out:
            out.append((t, name)); last = t
    return "\n".join(f"{fmt(t)} {name}" for t, name in out) if len(out) >= 3 else ""
