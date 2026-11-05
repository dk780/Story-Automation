"""python devops/run.py [--dry-run] [--force] [--episode N]
Makes the next unfinished episode of the DevOps series. Resumable: progress is kept in work/devops/epNN."""
import argparse, datetime, json, shutil, sys, uuid
from pathlib import Path
import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.append(str(HERE.parent))
import dv_script, dv_tts, dv_build, dv_anim

STATE = HERE / "state.json"


def load_state():
    s = json.loads(STATE.read_text()) if STATE.exists() else {}
    s.setdefault("done", []); s.setdefault("done_ids", [])
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--force", action="store_true"); ap.add_argument("--episode", type=int)
    a = ap.parse_args()
    cfg = yaml.safe_load(open(HERE / "config.yaml", encoding="utf-8"))
    series = yaml.safe_load(open(HERE / "series.yaml", encoding="utf-8"))
    state, today = load_state(), datetime.date.today().isoformat()
    if not (a.dry_run or a.force) and state.get("last_success") == today:
        print("An episode was already uploaded today. Nothing to do."); return
    todo = [e for e in series if e["n"] not in state["done"]]
    ep = next((e for e in series if e["n"] == a.episode), None) if a.episode else (todo[0] if todo else None)
    if not ep:
        print("All episodes of the series are finished. Add more topics to devops/series.yaml."); return
    nxt = next((e for e in series if e["n"] == ep["n"] + 1), None)

    work = Path("work/devops") / f"ep{ep['n']:02d}"
    meta_p = work / "meta.json"
    if work.exists():
        stale = True
        if meta_p.exists():
            m = json.loads(meta_p.read_text())
            stale = m["id"] in state["done_ids"] or (datetime.date.today() - datetime.date.fromisoformat(m["date"])).days > 2
        if stale:
            shutil.rmtree(work)
    work.mkdir(parents=True, exist_ok=True)
    if meta_p.exists():
        meta = json.loads(meta_p.read_text()); print(f"RESUMING episode {ep['n']}: {ep['title']}")
    else:
        meta = {"id": uuid.uuid4().hex, "date": today}; meta_p.write_text(json.dumps(meta))
        print(f"NEW episode {ep['n']} of {len(series)}: {ep['title']}")

    print("1/4 Script")
    sp = work / "script.json"
    if sp.exists():
        data = json.loads(sp.read_text(encoding="utf-8"))
    else:
        data = dv_script.generate(cfg, ep, nxt)
        sp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    intro = {"layout": "intro", "heading": "", "narration": data["intro_narration"], "emoji": ep["emoji"], "series": cfg["series_name"],
             "episode": f"EPISODE {ep['n']}", "title": ep["title"]}
    outro = {"layout": "outro", "heading": "", "narration": data["outro_narration"], "next": nxt["title"] if nxt else ""}
    scenes = [intro] + data["scenes"] + [outro]
    print(f"  {len(scenes)} scenes")

    print("2/4 Narration"); audio = dv_tts.narrate([s["narration"] for s in scenes], cfg, work)
    print("3/4 Rendering")
    video, thumb = work / "video.mp4", work / "thumb.jpg"
    secs, chapters = dv_build.build(scenes, audio, cfg, work, video, cfg.get("music"))
    print(f"  video length: {secs / 60:.1f} min")
    dv_anim.thumbnail(data["thumbnail_text"], ep["emoji"], f"EPISODE {ep['n']}", cfg["channel_name"], thumb)

    ch = dv_build.chapters_text(chapters)
    desc = data["description"] + (f"\n\n⏱ Chapters\n{ch}" if ch else "") + \
        f"\n\n📚 {cfg['series_name']}: episode {ep['n']} of {len(series)}. Watch the series in order to learn DevOps from scratch."
    if a.dry_run:
        print("Dry run: video at", video); print("\nTITLE:", data["title"], "\n\n" + desc); return
    from upload_youtube import upload
    print("4/4 Upload")
    print("Uploaded:", upload(video, thumb, data["title"], desc, data["tags"], cfg["privacy"], category="27"))
    state["done"].append(ep["n"]); state["done_ids"].append(meta["id"]); state["last_success"] = today
    STATE.write_text(json.dumps(state, indent=2))
    shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
